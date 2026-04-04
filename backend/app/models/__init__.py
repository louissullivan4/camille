# Import all models so Base.metadata is fully populated for migrations and test setup.
from app.models.assessment import Assessment  # noqa: F401
from app.models.document import Document  # noqa: F401
from app.models.external_signal import ExternalSignal  # noqa: F401
from app.models.organization import Organization  # noqa: F401
