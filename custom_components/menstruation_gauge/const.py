DOMAIN = "menstruation_gauge"

DATA_KEY = DOMAIN
STORE_VERSION = 1
STORE_KEY = f"{DOMAIN}.store"

DEFAULT_ENTITY_ID = "sensor.menstruation_gauge"
DEFAULT_PERIOD_DURATION_DAYS = 5

SERVICE_ADD_CYCLE_START = "add_cycle_start"
SERVICE_REMOVE_CYCLE_START = "remove_cycle_start"
SERVICE_SET_HISTORY = "set_history"
SERVICE_SET_PERIOD_DURATION = "set_period_duration"

ATTR_HISTORY = "history"
ATTR_GROUPED_CYCLE_STARTS = "grouped_cycle_starts"
ATTR_NEXT_PREDICTED_START = "next_predicted_start"
ATTR_DAYS_UNTIL_NEXT_START = "days_until_next_start"
ATTR_AVG_CYCLE_DAYS = "avg_cycle_days"
ATTR_PERIOD_DURATION_DAYS = "period_duration_days"
ATTR_FERTILE_WINDOW_START = "fertile_window_start"
ATTR_FERTILE_WINDOW_END = "fertile_window_end"
ATTR_LAST_UPDATED = "last_updated"
