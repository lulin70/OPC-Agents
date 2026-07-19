"""OPC-Agents DB migration scripts package.

Each module ``vN_<feature>.py`` exposes a ``migrate_vN(conn)`` function
that upgrades the schema from v(N-1) to vN. Migrations are invoked by
``opc_manager.data_manager._run_migrations`` in version order.
"""
