import { Link } from 'react-router';
import PageHeader from '../components/PageHeader';

export default function NotFound() {
  return (
    <>
      <PageHeader title="Page not found" subtitle="That route is not part of this console" />
      <div className="card max-w-[520px]">
        <p className="text-[13px] mb-4">The sidebar destination you opened does not exist.</p>
        <Link to="/" className="btn btn-primary no-underline">
          Return to dashboard
        </Link>
      </div>
    </>
  );
}
