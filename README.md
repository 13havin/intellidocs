# intellidocs

IntelliDocs is a document and research workspace currently under active development. Its FastAPI backend supports PostgreSQL-backed user registration, password-based login, profile retrieval, and workspace creation and retrieval using JWT bearer tokens. Workspace creators automatically become owners, and users can list and retrieve only workspaces they belong to. Document management, search, and AI-powered document analysis are planned.

Owners can add registered users to a workspace as owners, editors, or viewers, update member roles, and remove other members. Any member can leave their workspace, but the last owner cannot be demoted or removed. Members can list their workspace's members. Concurrent additions, role updates, and removals are serialized per workspace using PostgreSQL row locks.

See the [backend README](backend/README.md) for setup, database migrations, registration, login, bearer-token authentication, workspace and member API examples, and tests.
