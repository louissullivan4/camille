# Import all models so Base.metadata is fully populated for migrations and test setup.
from app.models.assessment import Assessment  # noqa: F401
from app.models.document import Document  # noqa: F401
from app.models.external_signal import ExternalSignal  # noqa: F401
from app.models.invitation import Invitation  # noqa: F401
from app.models.organization import Organization  # noqa: F401
from app.models.password_reset import PasswordResetToken  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.user_assessment_access import UserAssessmentAccess  # noqa: F401
