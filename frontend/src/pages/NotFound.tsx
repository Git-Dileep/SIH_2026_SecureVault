import { Link } from 'react-router';
import { SearchX } from 'lucide-react';
import EmptyState from '../components/EmptyState';

export default function NotFound() {
  return (
    <div className="h-full flex items-center justify-center p-8">
      <EmptyState
        icon={<SearchX size={32} />}
        title="Page Not Found"
        message="The requested route does not exist in the SecureVault console or you may not have permission to access it."
        action={
          <Link to="/" className="btn btn-primary no-underline hover-lift">
            Return to Dashboard
          </Link>
        }
      />
    </div>
  );
}
