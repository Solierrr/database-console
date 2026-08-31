-- View analitica de BI: ranking de tecnicos por servicos concluidos e
-- nota media, usando RANK() (window function) sobre uma CTE agregada.

CREATE OR REPLACE VIEW vw_technician_ranking AS
WITH technician_stats AS (
    SELECT
        t.id AS technician_key,
        p.name AS technician_name,
        COUNT(*) FILTER (WHERE ts.status = 'COMPLETED') AS completed_services,
        AVG(pr.rating) AS average_rating
    FROM technician t
    JOIN person p ON p.id = t.fk_person
    LEFT JOIN service_executor se ON se.fk_technician_affiliation IN (
        SELECT ta.id FROM technician_affiliation ta WHERE ta.fk_technician = t.id
    )
    LEFT JOIN technical_service ts ON ts.id = se.fk_service
    LEFT JOIN professional_review pr ON pr.fk_professional = t.id AND pr.active
    GROUP BY t.id, p.name
)
SELECT
    technician_key,
    technician_name,
    completed_services,
    ROUND(COALESCE(average_rating, 0), 2) AS average_rating,
    RANK() OVER (ORDER BY completed_services DESC, average_rating DESC) AS ranking
FROM technician_stats
ORDER BY ranking;
