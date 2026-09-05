import { Outlet } from 'react-router';
import LabBanner from './LabBanner';
import Navbar from './Navbar';
import Sidebar from './Sidebar';

export default function Layout() {
  return (
    <div className="flex min-h-screen" style={{ background: 'var(--color-bg-primary)' }}>
      <Sidebar />
      <main className="flex-1 ml-[240px]">
        <LabBanner />
        <Navbar />
        <div className="p-8 max-w-[1400px] mx-auto animate-fade-in">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
