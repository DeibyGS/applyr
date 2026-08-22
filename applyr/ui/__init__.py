"""Visual UI backend — optional `applyr[ui]` extra.

Nothing in this package may be imported at module level from anywhere in
`applyr.cli` or the base package: FastAPI/uvicorn are only installed when the
`[ui]` extra is present, and `import applyr.cli` must keep working with zero
dependencies beyond colorama (ADR-005) for every existing user. See
`applyr/ui/server.py` for the lazy-import boundary.
"""
