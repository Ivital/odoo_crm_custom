import base64
from datetime import timedelta

from lxml import html as lxml_html

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestPersonnelReports(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.ukraine = cls.env.ref("base.ua")

        cls.department = cls.env["hr.department"].create(
            {
                "name": "REPORT TEST Підрозділ",
                "company_id": cls.env.company.id,
            }
        )
        cls.job = cls.env["hr.job"].create(
            {
                "name": "REPORT TEST Посада",
                "company_id": cls.env.company.id,
            }
        )
        cls.employee = cls.env["hr.employee"].create(
            {
                "name": "Працівник Для Друку Тестовий",
                "company_id": cls.env.company.id,
                "identification_id": "REPORT-001",
                "department_id": cls.department.id,
                "job_id": cls.job.id,
                "birthday": "1980-05-10",
                "gender": "male",
                "country_id": cls.ukraine.id,
                "private_country_id": cls.ukraine.id,
                "private_city": "Кривий Ріг",
                "private_street": "вул. Тестова, 1",
                "l10n_ua_p2_card_number": "P2-TEST-001",
                "l10n_ua_p2_card_date": fields.Date.today(),
                "l10n_ua_p2_registered_address": "м. Кривий Ріг, тестова адреса",
            }
        )
        cls.leave_type = cls.env["hr.leave.type"].create(
            {
                "name": "REPORT TEST Відпустка",
                "requires_allocation": "no",
                "leave_validation_type": "no_validation",
            }
        )

    def _order(self, order_type, vals):
        line_vals = {
            "employee_id": self.employee.id,
            "effective_date": fields.Date.today(),
            **vals,
        }
        return self.env["hr.personnel.order"].create(
            {
                "number": f"REPORT-{order_type.upper()}",
                "order_type": order_type,
                "subject": f"REPORT TEST {order_type}",
                "company_id": self.env.company.id,
                "line_ids": [(0, 0, line_vals)],
            }
        )

    def _render(self, report_xmlid, records):
        html, _ = self.env["ir.actions.report"]._render_qweb_html(
            report_xmlid,
            records.ids,
        )
        self.assertTrue(html)
        return html.decode() if isinstance(html, bytes) else html

    def _assert_standard_pdf_layout(
        self,
        report_xmlid,
        records,
        html,
        *,
        expected_pages,
    ):
        root = lxml_html.fromstring(html)

        articles = root.xpath(
            "//div[contains("
            "concat(' ', normalize-space(@class), ' '), "
            "' article '"
            ")]"
        )
        self.assertEqual(len(articles), 1)

        pages = articles[0].xpath(
            ".//div[contains("
            "concat(' ', normalize-space(@class), ' '), "
            "' page '"
            ")]"
        )
        self.assertEqual(len(pages), expected_pages)

        for page in pages:
            normalized_style = page.get("style", "").replace(" ", "")
            self.assertIn(
                "font-family:'TimesNewRoman'",
                normalized_style,
            )
            self.assertNotIn(
                "font-family:'DejaVuSans'",
                normalized_style,
            )

        forced_two_page_reports = {
            "hr_personnel_order_ua.action_report_personal_card_p2",
        }

        if report_xmlid in forced_two_page_reports:
            self.assertEqual(len(pages), 2)
            second_page_style = pages[1].get("style", "")
            self.assertIn(
                "page-break-before:always",
                second_page_style.replace(" ", ""),
            )

        report = self.env.ref(report_xmlid)

        (
            bodies,
            _res_ids,
            _header,
            _footer,
            _paperformat_args,
        ) = report._prepare_html(
            html,
            report.model,
        )

        self.assertEqual(len(bodies), 1)

        prepared_body = bodies[0]
        if isinstance(prepared_body, bytes):
            prepared_body = prepared_body.decode("utf-8")
        else:
            prepared_body = str(prepared_body)

        self.assertIn('charset="utf-8"', prepared_body)

    def test_p1_report_action_and_html(self):
        order = self._order(
            "hire",
            {
                "department_id": self.department.id,
                "job_id": self.job.id,
                "wage": 25000.0,
                "work_type": "main",
                "weekly_hours": 40.0,
            },
        )

        action = order.action_print_p1()
        self.assertEqual(
            action["report_name"],
            "hr_personnel_order_ua.report_personnel_order_p1",
        )

        html = self._render(
            "hr_personnel_order_ua.action_report_personnel_order_p1",
            order,
        )
        self.assertIn("про прийняття на роботу", html)
        self.assertIn("Працівник Для Друку Тестовий", html)
        self.assertIn(
            'умови праці (згідно атестації робочого місця)',
            html,
        )
        self.assertIn("грн.", html)
        self.assertIn("коп.", html)
        self.assertNotIn("Типова форма № П-1 — друга сторона", html)
        self.assertNotIn("Результати медичного огляду", html)
        self.assertNotIn("☐", html)
        self.assertNotIn("☒", html)
        self.assertEqual(html.count("l10n-ua-checkbox"), 15)
        self._assert_standard_pdf_layout(
            "hr_personnel_order_ua.action_report_personnel_order_p1",
            order,
            html,
            expected_pages=1,
        )

    def test_hire_internal_appendix_action_and_html(self):
        order = self._order(
            "hire",
            {
                "department_id": self.department.id,
                "job_id": self.job.id,
                "wage": 25000.0,
                "work_type": "main",
                "weekly_hours": 40.0,
            },
        )

        action = order.action_print_hire_appendix()

        self.assertEqual(
            action["report_name"],
            "hr_personnel_order_ua.report_personnel_order_hire_appendix",
        )

        html = self._render(
            "hr_personnel_order_ua.action_report_personnel_order_hire_appendix",
            order,
        )

        self.assertIn("ВНУТРІШНІЙ ДОДАТОК", html)
        self.assertIn(
            "Не є другою стороною типової форми № П-1",
            html,
        )
        self.assertIn("Результати медичного огляду", html)
        self.assertIn("Результати проходження інструктажів", html)

        self._assert_standard_pdf_layout(
            "hr_personnel_order_ua.action_report_personnel_order_hire_appendix",
            order,
            html,
            expected_pages=1,
        )

    def test_p3_report_action_and_html(self):
        start = fields.Date.today() + timedelta(days=10)
        end = start + timedelta(days=4)

        order = self._order(
            "leave",
            {
                "leave_type_id": self.leave_type.id,
                "work_period_from": fields.Date.today() - timedelta(days=365),
                "work_period_to": fields.Date.today() - timedelta(days=1),
                "leave_date_from": start,
                "leave_date_to": end,
                "health_assistance": True,
            },
        )

        action = order.action_print_p3()
        self.assertEqual(
            action["report_name"],
            "hr_personnel_order_ua.report_personnel_order_p3",
        )

        html = self._render(
            "hr_personnel_order_ua.action_report_personnel_order_p3",
            order,
        )
        self.assertIn("про надання відпустки", html)
        self.assertIn("5", html)
        self.assertIn("календарних днів", html)
        self.assertNotIn("календарних дні(в)", html)
        self.assertNotIn("☐", html)
        self.assertNotIn("☒", html)
        self.assertEqual(html.count("l10n-ua-checkbox"), 1)
        self._assert_standard_pdf_layout(
            "hr_personnel_order_ua.action_report_personnel_order_p3",
            order,
            html,
            expected_pages=1,
        )

    def test_p4_report_action_and_html(self):
        order = self._order(
            "termination",
            {
                "legal_reason": "За власним бажанням",
                "legal_article": "ст. 38 КЗпП України",
                "termination_basis": "Заява працівника",
                "unused_leave_days": 15.0,
                "severance_amount": 1000.0,
            },
        )

        action = order.action_print_p4()
        self.assertEqual(
            action["report_name"],
            "hr_personnel_order_ua.report_personnel_order_p4",
        )

        html = self._render(
            "hr_personnel_order_ua.action_report_personnel_order_p4",
            order,
        )
        self.assertIn("про припинення трудового договору", html)
        self.assertIn("ст. 38 КЗпП України", html)
        self.assertIn("Вихідна допомога", html)
        self.assertIn("грн.", html)
        self.assertIn("коп.", html)
        self.assertIn("Додатково:", html)
        self.assertEqual(html.count("l10n-ua-checkbox"), 1)

        p4_text = " ".join(
            lxml_html.fromstring(html).text_content().split()
        )
        self.assertIn(
            "За власним бажанням, ст. 38 КЗпП України",
            p4_text,
        )
        self._assert_standard_pdf_layout(
            "hr_personnel_order_ua.action_report_personnel_order_p4",
            order,
            html,
            expected_pages=1,
        )

    def test_p2_report_action_and_html(self):
        action = self.employee.action_print_personal_card_p2()
        self.assertEqual(
            action["report_name"],
            "hr_personnel_order_ua.report_personal_card_p2",
        )

        report = self.env.ref(
            "hr_personnel_order_ua.action_report_personal_card_p2"
        )
        portrait = self.env.ref(
            "hr_personnel_order_ua.paperformat_hr_personnel_a4_portrait"
        )

        self.assertEqual(report.paperformat_id, portrait)
        self.assertEqual(report.paperformat_id.orientation, "Portrait")

        html = self._render(
            "hr_personnel_order_ua.action_report_personal_card_p2",
            self.employee,
        )
        self.assertIn("ОСОБОВА КАРТКА ПРАЦІВНИКА", html)
        self.assertIn("Кривий Ріг", html)
        self.assertIn("Чоловіча", html)
        self.assertIn("Україна", html)
        self.assertIn("Стать", html)
        self.assertIn("(чоловіча, жіноча)", html)
        self.assertIn("Вид роботи", html)
        self.assertIn("(основна, за сумісництвом)", html)
        self.assertIn(
            "Спеціальність (професія) за дипломом (свідоцтвом)",
            html,
        )
        self.assertIn(
            "Кваліфікація за дипломом (свідоцтвом)",
            html,
        )
        self.assertIn(
            "(денна, вечірня, заочна)",
            html,
        )
        self.assertIn(
            "Назва документа, що посвідчує професійну освіту, ким виданий",
            html,
        )
        self.assertIn("Підпис працівника", html)
        self.assertNotIn("Кваліфікація / форма навчання", html)

        p2_root = lxml_html.fromstring(html)
        photo_cells = p2_root.xpath(
            "//*[contains("
            "concat(' ', normalize-space(@class), ' '), "
            "' p2-photo-cell '"
            ")]"
        )
        self.assertEqual(len(photo_cells), 1)
        self.assertNotIn(
            "position:absolute",
            photo_cells[0].get("style", "").replace(" ", ""),
        )

        self._assert_standard_pdf_layout(
            "hr_personnel_order_ua.action_report_personal_card_p2",
            self.employee,
            html,
            expected_pages=2,
        )

    def test_wrong_order_type_is_rejected(self):
        order = self._order(
            "termination",
            {
                "legal_reason": "Тест",
            },
        )

        with self.assertRaises(ValidationError):
            order.action_print_p1()

        with self.assertRaises(ValidationError):
            order.action_print_p3()

    def test_private_address_helper(self):
        address = self.employee._l10n_ua_report_private_address()
        self.assertIn("Кривий Ріг", address)
        self.assertIn("вул. Тестова, 1", address)
        self.assertIn("Україна", address)
        self.assertNotIn("Ukraine", address)

    def test_report_photo_filters_svg_avatar(self):
        svg = base64.b64encode(
            b'<svg xmlns="http://www.w3.org/2000/svg">'
            b'<text>AB</text>'
            b'</svg>'
        )
        raster = base64.b64encode(
            b"\x89PNG\r\n\x1a\n"
            b"report-photo-test"
        )

        self.assertTrue(
            self.employee._l10n_ua_report_image_is_svg(svg)
        )
        self.assertFalse(
            self.employee._l10n_ua_report_image_is_svg(raster)
        )
