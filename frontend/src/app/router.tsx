import { createBrowserRouter } from 'react-router-dom'
import { CommandCenter } from '../components/layout/CommandCenter'
import { AlertsPage } from '../features/alerts/AlertsPage'
import { AuditPage } from '../features/audit/AuditPage'
import { IngestionPage } from '../features/ingestion/IngestionPage'
import { OverviewPage } from '../features/overview/OverviewPage'
import { SimulationPage } from '../features/simulation/SimulationPage'
import { IntegrationsPage } from '../features/integrations/IntegrationsPage'

export const router = createBrowserRouter([{ path: '/', element: <CommandCenter />, children: [
  { index: true, element: <OverviewPage /> },
  { path: 'alerts', element: <AlertsPage /> },
  { path: 'simulation', element: <SimulationPage /> },
  { path: 'ingestion', element: <IngestionPage /> },
  { path: 'audit', element: <AuditPage /> },
  { path: 'integrations', element: <IntegrationsPage /> },
] }])
