# Danphe EMR integration requirements

## Evidence found

The checked-in Danphe source is a legacy ASP.NET Core application targeting
`.NET Framework 4.6.1`. `Startup.cs` uses `SqlConnectionStringBuilder`, and the
database scripts create SQL Server databases and use SQL Server-specific
objects. The application configures JWT bearer authentication and Swagger.

The source contains broad MVC controller APIs under `api/[controller]`,
including admission, patient, inventory, and dashboard controllers. No
PulseReady-specific endpoint, approved export, read replica, CDC contract, or
FHIR endpoint was identified in the inspected source.

The repository does not contain the ignored Danphe `appsettings.json`, a
development connection string, a reachable SQL Server instance, or an
administrator-approved operational view schema. The exact SQL Server version
is therefore unverified.

## Current implementation

`app/integrations/danphe.py` defines:

- `OperationalDataProvider`, a read-only provider interface.
- `SyntheticOperationalDataProvider`, used for deterministic local tests.
- `DanpheOperationalDataProvider`, disabled by default and fail-closed.
- Pydantic validation for facility, signal, timestamp, value, unit, source,
  provenance, retrieval time, and freshness status.

No API endpoint accepts SQL, table names, arbitrary URLs, or patient data. No
Danphe connection is opened and no Danphe table is modified.

## Required authorization before enabling Danphe

An administrator must provide, outside source control:

1. A read-only SQL Server development connection or approved read replica.
2. The exact SQL Server version and driver supported on the deployment host.
3. One fixed view or stored procedure containing only approved operational
   fields, with facility and timestamp filters.
4. A field-level mapping for staffing, supplies, capacity, system telemetry,
   units, source timestamps, and freshness semantics.
5. Tenant/facility authorization rules and a data-minimization review.
6. A non-production validation run against synthetic or explicitly authorized
   development data.

Only after those items are reviewed should a bounded SQL Server adapter be
implemented. It must use a fixed query, parameterized facility/time filters,
read-only credentials, query and row limits, connection/query timeouts, and
tests against a disposable development database.

## Configuration

The bridge is disabled by default:

```text
DANPHE_ENABLED=false
DANPHE_CONNECTION_STRING=YOUR_READ_ONLY_SQLSERVER_CONNECTION_STRING_HERE
DANPHE_APPROVED_VIEW=YOUR_APPROVED_VIEW_NAME_HERE
```

These values are configuration slots only. They do not establish a live
connection. Keep local `.env` files out of version control and never place
Danphe credentials in the frontend.

## Verification status

The local synthetic boundary is tested. Live Danphe connectivity is **not
verified** because the required authorized development environment and data
contract are unavailable.
