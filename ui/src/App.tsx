import { createBrowserRouter, Navigate, RouterProvider, useLocation } from 'react-router';
import { AppLayout } from './components/AppLayout';
import { Callout } from './components/Callout';
import { AnalysisReviewPage } from './pages/AnalysisReviewPage';
import { DesignReviewPage } from './pages/DesignReviewPage';
import { NewRequestPage } from './pages/NewRequestPage';
import { ProgressPage } from './pages/ProgressPage';
import { QueryPage } from './pages/QueryPage';
import { ResultPage } from './pages/ResultPage';

/** 쿼리(확장 요청 미리 채우기)가 바뀌면 폼을 새로 그린다 */
function NewRequestRoute() {
  const { search } = useLocation();
  return <NewRequestPage key={search} />;
}

function NotFound() {
  return (
    <Callout tone="error" icon="error" title="없는 화면입니다">
      왼쪽 메뉴에서 사이트를 고르거나 새 요청을 시작하세요.
    </Callout>
  );
}

const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate to="/new" replace /> },
      { path: 'new', element: <NewRequestRoute /> },
      { path: 'sites/:alias', element: <ProgressPage /> },
      { path: 'sites/:alias/analysis', element: <AnalysisReviewPage /> },
      { path: 'sites/:alias/design', element: <DesignReviewPage /> },
      { path: 'sites/:alias/result', element: <ResultPage /> },
      { path: 'query', element: <QueryPage /> },
      { path: '*', element: <NotFound /> },
    ],
  },
]);

export function App() {
  return <RouterProvider router={router} />;
}
