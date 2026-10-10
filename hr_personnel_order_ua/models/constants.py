ENGINE_CONTEXT_KEY = "hr_personnel_order_engine"

ORDER_TYPE_SELECTION = [
    ("hire", "Прийняття на роботу"),
    ("transfer", "Переведення"),
    ("position_change", "Зміна посади"),
    ("department_change", "Зміна підрозділу"),
    ("salary_change", "Зміна оплати праці"),
    ("schedule_change", "Зміна графіка роботи"),
    ("employment_condition_change", "Зміна умов праці"),
    ("leave", "Відпустка"),
    ("termination", "Припинення трудового договору"),
    ("bonus", "Преміювання / матеріальна допомога"),
    ("business_trip", "Відрядження"),
    ("disciplinary", "Дисциплінарний наказ"),
    ("other", "Інший кадровий наказ"),
]

WORK_TYPE_SELECTION = [
    ("main", "Основне місце роботи"),
    ("part_time", "За сумісництвом"),
]

HIRE_CONDITION_SELECTION = [
    ("competition", "На конкурсній основі"),
    ("contract", "За умовами контракту"),
    ("fixed_work", "На час виконання певної роботи"),
    ("replacement", "На період відсутності основного працівника"),
    ("personnel_reserve", "Із кадрового резерву"),
    ("internship", "За результатами успішного стажування"),
    ("transfer", "Переведення"),
    ("other", "Інша умова"),
]
