"""Import every SQLAlchemy model module so Base.metadata is fully populated
before Alembic autogenerate or create_all runs. Import this module (not the
individual model modules) wherever full metadata is required."""

from app.domain.agents import models as _agents_models  # noqa: F401
from app.domain.commercial import models as _commercial_models  # noqa: F401
from app.domain.content import models as _content_models  # noqa: F401
from app.domain.creator import models as _creator_models  # noqa: F401
from app.domain.experiments import models as _experiments_models  # noqa: F401
from app.domain.performance import models as _performance_models  # noqa: F401
from app.domain.pipeline import models as _pipeline_models  # noqa: F401
from app.domain.research import models as _research_models  # noqa: F401
from app.domain.strategy import models as _strategy_models  # noqa: F401
from app.infrastructure.db.base import Base

__all__ = ["Base"]
