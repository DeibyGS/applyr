import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import { AppShell } from "@/layout/AppShell";
import OfficePage from "@/pages/OfficePage";
import OffersPage from "@/pages/OffersPage";
import InterviewsPage from "@/pages/InterviewsPage";
import ArchivePage from "@/pages/ArchivePage";
import AnalyticsPage from "@/pages/AnalyticsPage";
import SettingsPage from "@/pages/SettingsPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<Navigate to="/office" replace />} />
          <Route path="office" element={<OfficePage />} />
          <Route path="offers" element={<OffersPage />} />
          <Route path="agents" element={<Navigate to="/office" replace />} />
          <Route path="interviews" element={<InterviewsPage />} />
          <Route path="archive" element={<ArchivePage />} />
          <Route path="analytics" element={<AnalyticsPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
