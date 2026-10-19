"""Provider dispatch for supported canonical entity types."""
from . import isolved, prismhr, ukg_ready

ADAPTERS = {"prismhr": prismhr, "isolved": isolved, "ukg-ready": ukg_ready}
ENTITIES = ("company", "employee", "direct_deposit", "deduction", "payroll_run", "paycheck", "compensation", "demographics", "pay_info", "custom_fields", "payroll")
