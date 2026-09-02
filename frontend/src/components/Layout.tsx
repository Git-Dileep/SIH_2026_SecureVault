import { Outlet } from 'react-router';
import Sidebar from './Sidebar';

export default function Layout() {
  return (
    <div className="flex min-h-screen" style={{ background: 'var(--color-bg-primary)' }}>
      <Sidebar />
      <main className="flex-1 ml-[260px]">
        <div className="p-8 max-w-[1400px] mx-auto animate-fade-in">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
