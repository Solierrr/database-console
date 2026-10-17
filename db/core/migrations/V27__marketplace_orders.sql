-- Carrinho e pedidos de compra de unidades de ofertas. Os pagamentos são fictícios: nenhum valor real é movimentado.
CREATE TABLE IF NOT EXISTS cart (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_users   uuid NOT NULL UNIQUE REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cart_item (
    id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_cart   uuid NOT NULL REFERENCES cart(id) ON DELETE CASCADE,
    fk_offer  uuid NOT NULL REFERENCES offer(id) ON DELETE CASCADE,
    quantity  integer NOT NULL CHECK (quantity > 0),
    added_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_cart_item_offer UNIQUE (fk_cart, fk_offer)
);

CREATE TABLE IF NOT EXISTS purchase_order (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_buyer       uuid NOT NULL REFERENCES users(id),
    status         varchar(16) NOT NULL DEFAULT 'PAID' CHECK (status IN ('PAID', 'CANCELED')),
    subtotal       numeric(12,2) NOT NULL CHECK (subtotal >= 0),
    fee_percentage numeric(6,5) NOT NULL CHECK (fee_percentage >= 0 AND fee_percentage <= 1),
    fee_amount     numeric(12,2) NOT NULL CHECK (fee_amount >= 0),
    total          numeric(12,2) NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now(),
    canceled_at    timestamptz,
    canceled_by    uuid REFERENCES users(id),
    CONSTRAINT ck_purchase_order_total CHECK (total = subtotal + fee_amount),
    CONSTRAINT ck_purchase_order_canceled CHECK ((status = 'CANCELED') = (canceled_at IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS order_item (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_order            uuid NOT NULL REFERENCES purchase_order(id) ON DELETE CASCADE,
    fk_offer            uuid REFERENCES offer(id) ON DELETE SET NULL,
    fk_supplier         uuid NOT NULL REFERENCES supplier(id),
    offer_slug          varchar(160) NOT NULL,
    model_name          varchar(255) NOT NULL,
    unit_price          numeric(12,2) NOT NULL CHECK (unit_price >= 0),
    discount_percentage numeric(5,2) NOT NULL DEFAULT 0 CHECK (discount_percentage >= 0 AND discount_percentage <= 100),
    net_unit_price      numeric(12,2) NOT NULL,
    quantity            integer NOT NULL CHECK (quantity > 0),
    line_total          numeric(12,2) NOT NULL,
    CONSTRAINT ck_order_item_net_price CHECK (net_unit_price = round(unit_price * (100 - discount_percentage) / 100, 2)),
    CONSTRAINT ck_order_item_line_total CHECK (line_total = net_unit_price * quantity)
);

CREATE TABLE IF NOT EXISTS order_payment (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fk_order    uuid NOT NULL UNIQUE REFERENCES purchase_order(id) ON DELETE CASCADE,
    method      payment_method NOT NULL,
    amount      numeric(12,2) NOT NULL CHECK (amount >= 0),
    status      varchar(16) NOT NULL DEFAULT 'PAID' CHECK (status IN ('PAID', 'REFUNDED')),
    paid_at     timestamptz NOT NULL DEFAULT now(),
    refunded_at timestamptz,
    CONSTRAINT ck_order_payment_refunded CHECK ((status = 'REFUNDED') = (refunded_at IS NOT NULL))
);

-- Usuário de empresa fornecedora não compra, salvo se for profissional registrado e aprovado. Ninguém compra de uma
-- empresa fornecedora à qual pertence.
CREATE OR REPLACE FUNCTION enforce_order_buyer_eligibility() RETURNS trigger AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM user_company uc JOIN supplier s ON s.fk_company = uc.fk_company WHERE uc.fk_users = NEW.fk_buyer)
     AND NOT EXISTS (SELECT 1 FROM person p JOIN technician t ON t.fk_person = p.id WHERE p.fk_users = NEW.fk_buyer AND t.status = 'APPROVED') THEN
    RAISE EXCEPTION 'Usuário de empresa fornecedora não pode comprar' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS purchase_order_buyer_not_supplier ON purchase_order;
DROP TRIGGER IF EXISTS purchase_order_buyer_eligibility ON purchase_order;
CREATE TRIGGER purchase_order_buyer_eligibility BEFORE INSERT ON purchase_order FOR EACH ROW EXECUTE FUNCTION enforce_order_buyer_eligibility();

CREATE OR REPLACE FUNCTION enforce_order_item_not_own_supplier() RETURNS trigger AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM purchase_order o JOIN user_company uc ON uc.fk_users = o.fk_buyer JOIN supplier s ON s.fk_company = uc.fk_company
             WHERE o.id = NEW.fk_order AND s.id = NEW.fk_supplier) THEN
    RAISE EXCEPTION 'Não é possível comprar de uma empresa à qual o comprador pertence' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS order_item_not_own_supplier ON order_item;
CREATE TRIGGER order_item_not_own_supplier BEFORE INSERT ON order_item FOR EACH ROW EXECUTE FUNCTION enforce_order_item_not_own_supplier();

CREATE INDEX IF NOT EXISTS idx_purchase_order_buyer ON purchase_order (fk_buyer, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_order_item_order ON order_item (fk_order);
CREATE INDEX IF NOT EXISTS idx_order_item_supplier ON order_item (fk_supplier, fk_order);
CREATE INDEX IF NOT EXISTS idx_order_item_offer ON order_item (fk_offer) WHERE fk_offer IS NOT NULL;
