import enum


class FrequencyType(enum.Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"


class RecurrenceType(enum.Enum):
    ONETIME = "ONETIME"
    RECURRING = "RECURRING"
    EXCEPTION = "EXCEPTION"
