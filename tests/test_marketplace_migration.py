import importlib.util
import os
from pathlib import Path
import unittest
import uuid

import psycopg2
from psycopg2 import sql

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('migrate', ROOT / 'scripts/migrate.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


@unittest.skipUnless(os.environ.get('SOLARIA_TEST_PG_DSN'), 'Set an isolated PostgreSQL test DSN')
class MarketplaceMigrationTest(unittest.TestCase):
    def setUp(self):
        self.connection = psycopg2.connect(os.environ['SOLARIA_TEST_PG_DSN'])
        self.schema = 'test_' + uuid.uuid4().hex
        with self.connection.cursor() as cursor:
            cursor.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(self.schema)))
            cursor.execute(sql.SQL('SET search_path TO {}, public').format(sql.Identifier(self.schema)))
        self.connection.commit()
        runner.migrate(self.connection, 'core')
        self.execute((ROOT / 'db/core/seed.sql').read_text(encoding='utf-8-sig'))
        self.connection.commit()
        self.buyer = self.execute("SELECT uc.fk_users FROM user_company uc JOIN company c ON c.id = uc.fk_company WHERE c.type = 'DEMANDANT' LIMIT 1")[0][0]
        self.supplier_user = self.execute("SELECT uc.fk_users FROM user_company uc JOIN supplier s ON s.fk_company = uc.fk_company LIMIT 1")[0][0]
        self.offer, self.supplier = self.execute('SELECT id, fk_supplier FROM offer LIMIT 1')[0]

    def tearDown(self):
        self.connection.rollback()
        with self.connection.cursor() as cursor:
            cursor.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))
        self.connection.commit()
        self.connection.close()

    def execute(self, statement, parameters=None):
        with self.connection.cursor() as cursor:
            cursor.execute(statement, parameters)
            return cursor.fetchall() if cursor.description else None

    def rejects(self, code, statement, parameters=None):
        with self.assertRaises(psycopg2.Error) as raised:
            self.execute(statement, parameters)
        self.assertEqual(code, raised.exception.pgcode)
        self.connection.rollback()

    def order(self, buyer=None, subtotal='100.00', fee='0.50', total='100.50'):
        identifier = self.execute(
            'INSERT INTO purchase_order(fk_buyer, subtotal, fee_percentage, fee_amount, total) VALUES (%s, %s, 0.005, %s, %s) RETURNING id',
            (buyer or self.buyer, subtotal, fee, total),
        )[0][0]
        self.connection.commit()
        return identifier

    def test_tables_and_permissions_exist(self):
        for table in ('cart', 'cart_item', 'purchase_order', 'order_item', 'order_payment'):
            self.assertEqual(1, self.execute('SELECT count(*) FROM information_schema.tables WHERE table_schema = current_schema() AND table_name = %s', (table,))[0][0])
        names = {row[0] for row in self.execute("SELECT permission_name FROM permission WHERE permission_name LIKE '% /api/cart%' OR permission_name LIKE '% /api/orders%' OR permission_name LIKE '% /api/sales' OR permission_name = 'GET /api/subscription' OR permission_name = 'POST /api/charges/{id}/payment'")}
        self.assertEqual(
            {'GET /api/cart', 'PUT /api/cart/items/{offerId}', 'DELETE /api/cart/items/{offerId}', 'POST /api/orders', 'GET /api/orders',
             'GET /api/orders/{id}', 'PATCH /api/orders/{id}/cancel', 'GET /api/sales', 'GET /api/subscription', 'POST /api/charges/{id}/payment'},
            names,
        )

    def test_one_cart_per_user_and_one_line_per_offer_with_positive_quantity(self):
        cart = self.execute('INSERT INTO cart(fk_users) VALUES (%s) RETURNING id', (self.buyer,))[0][0]
        self.connection.commit()
        self.rejects('23505', 'INSERT INTO cart(fk_users) VALUES (%s)', (self.buyer,))
        self.execute('INSERT INTO cart_item(fk_cart, fk_offer, quantity) VALUES (%s, %s, 2)', (cart, self.offer))
        self.connection.commit()
        self.rejects('23505', 'INSERT INTO cart_item(fk_cart, fk_offer, quantity) VALUES (%s, %s, 1)', (cart, self.offer))
        self.rejects('23514', 'UPDATE cart_item SET quantity = 0 WHERE fk_cart = %s', (cart,))

    def test_deleting_an_offer_removes_it_from_carts_but_keeps_the_order_history(self):
        cart = self.execute('INSERT INTO cart(fk_users) VALUES (%s) RETURNING id', (self.buyer,))[0][0]
        self.execute('INSERT INTO cart_item(fk_cart, fk_offer, quantity) VALUES (%s, %s, 1)', (cart, self.offer))
        order = self.order(subtotal='90.00', fee='0.45', total='90.45')
        self.execute(
            "INSERT INTO order_item(fk_order, fk_offer, fk_supplier, offer_slug, model_name, unit_price, discount_percentage, net_unit_price, quantity, line_total) VALUES (%s, %s, %s, 'oferta', 'ST-450W', 100, 10, 90, 1, 90)",
            (order, self.offer, self.supplier),
        )
        self.execute('DELETE FROM proposal_unit')
        self.execute('DELETE FROM proposal_item')
        self.execute('DELETE FROM offer_translation')
        self.execute('DELETE FROM offer WHERE id = %s', (self.offer,))
        self.assertEqual(0, self.execute('SELECT count(*) FROM cart_item')[0][0])
        item = self.execute('SELECT fk_offer, model_name FROM order_item WHERE fk_order = %s', (order,))[0]
        self.assertEqual((None, 'ST-450W'), item)

    def test_order_totals_are_consistent(self):
        self.rejects('23514', 'INSERT INTO purchase_order(fk_buyer, subtotal, fee_percentage, fee_amount, total) VALUES (%s, 100, 0.005, 0.50, 100.00)', (self.buyer,))
        self.rejects('23514', "INSERT INTO purchase_order(fk_buyer, status, subtotal, fee_percentage, fee_amount, total) VALUES (%s, 'CANCELED', 100, 0.005, 0.50, 100.50)", (self.buyer,))
        order = self.order()
        self.assertEqual('PAID', self.execute('SELECT status FROM purchase_order WHERE id = %s', (order,))[0][0])

    def test_item_price_and_total_follow_the_discount(self):
        order = self.order()
        statement = "INSERT INTO order_item(fk_order, fk_offer, fk_supplier, offer_slug, model_name, unit_price, discount_percentage, net_unit_price, quantity, line_total) VALUES (%s, %s, %s, 'oferta', 'ST-450W', 99.99, 12.5, %s, %s, %s)"
        self.rejects('23514', statement, (order, self.offer, self.supplier, '90.00', 1, '90.00'))
        self.rejects('23514', statement, (order, self.offer, self.supplier, '87.49', 2, '170.00'))
        self.rejects('23514', statement, (order, self.offer, self.supplier, '87.49', 0, '0.00'))
        self.execute(statement, (order, self.offer, self.supplier, '87.49', 2, '174.98'))

    def test_one_payment_per_order_and_refund_state_is_consistent(self):
        order = self.order()
        self.execute("INSERT INTO order_payment(fk_order, method, amount) VALUES (%s, 'PIX', 100.50)", (order,))
        self.connection.commit()
        self.rejects('23505', "INSERT INTO order_payment(fk_order, method, amount) VALUES (%s, 'CREDIT_CARD', 100.50)", (order,))
        self.rejects('23514', "UPDATE order_payment SET status = 'REFUNDED' WHERE fk_order = %s", (order,))
        self.execute("UPDATE order_payment SET status = 'REFUNDED', refunded_at = now() WHERE fk_order = %s", (order,))

    def test_a_supplier_user_cannot_buy(self):
        self.rejects('23514', 'INSERT INTO purchase_order(fk_buyer, subtotal, fee_percentage, fee_amount, total) VALUES (%s, 100, 0.005, 0.50, 100.50)', (self.supplier_user,))

    def make_professional(self, user, status='APPROVED'):
        person = self.execute("INSERT INTO person(id, fk_users, name, cpf, birth_date) VALUES (gen_random_uuid(), %s, 'Profissional', '52998224725', '1990-01-01') RETURNING id", (user,))[0][0]
        self.execute("INSERT INTO technician(id, fk_person, crea, slug, status) VALUES (gen_random_uuid(), %s, 'CREA-SP 123', %s, %s)", (person, 'prof-' + uuid.uuid4().hex[:8], status))
        self.connection.commit()

    def test_an_approved_professional_of_a_supplier_company_can_buy_from_others_but_not_from_it(self):
        self.make_professional(self.supplier_user)
        order = self.order(buyer=self.supplier_user)
        statement = "INSERT INTO order_item(fk_order, fk_offer, fk_supplier, offer_slug, model_name, unit_price, discount_percentage, net_unit_price, quantity, line_total) VALUES (%s, NULL, %s, 'oferta', 'ST-450W', 100, 0, 100, 1, 100)"
        self.rejects('23514', statement, (order, self.supplier))

    def test_a_professional_that_is_not_approved_cannot_buy_for_a_supplier_company(self):
        self.make_professional(self.supplier_user, status='UNDER_ANALYSIS')
        self.rejects('23514', 'INSERT INTO purchase_order(fk_buyer, subtotal, fee_percentage, fee_amount, total) VALUES (%s, 100, 0.005, 0.50, 100.50)', (self.supplier_user,))

    def test_migration_can_be_reapplied_without_changing_data(self):
        order = self.order()
        self.connection.commit()
        runner.migrate(self.connection, 'core')
        self.assertEqual(1, self.execute('SELECT count(*) FROM purchase_order WHERE id = %s', (order,))[0][0])


if __name__ == '__main__':
    unittest.main()
