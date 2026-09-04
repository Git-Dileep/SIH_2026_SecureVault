import { Navigate } from 'react-router';
import { getToken } from '../auth';
import Layout from './Layout';

export default function RequireAuth() {
  if (!getToken()) {
    return <Navigate to="/login" replace />;
  }
  return <Layout />;
}
