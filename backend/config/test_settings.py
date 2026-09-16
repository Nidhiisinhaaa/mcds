"""
Settings module used only for the test suite (see pytest.ini's
DJANGO_SETTINGS_MODULE). Composes the real settings, then overrides GROQ_MOCK
so a plain `pytest` run is always deterministic and network-free, regardless
of what backend/.env happens to have GROQ_MOCK set to for a developer's own
manual/live-API testing.

Setting this via os.environ in a conftest.py does NOT work here: pytest-django
forces config.settings to load (running its dotenv.load_dotenv() and fixing
GROQ_MOCK's value) inside its own pytest_load_initial_conftests hook, which
runs before any project conftest.py is even imported - by the time a
conftest.py could set the env var, config.settings has already read and
cached the old value. Pointing DJANGO_SETTINGS_MODULE at this module instead
sidesteps that ordering problem entirely.

A test that genuinely needs live-API behaviour should flip
settings.GROQ_MOCK back via the `settings` pytest fixture for just that test
(see core/tests.py for examples) rather than relying on this default.
"""

from config.settings import *  # noqa: F401,F403

GROQ_MOCK = True
