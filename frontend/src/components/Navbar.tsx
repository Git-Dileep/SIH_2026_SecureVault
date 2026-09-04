import { NavLink } from 'react-router';

const LINKS = [
  { to: '/demo/delete-recover', label: 'Delete → Recover' },
  { to: '/erasure/ssd', label: 'SSD Erasure' },
  { to: '/ai/classifier', label: 'AI Classifier' },
  { to: '/audit/chain', label: 'Audit Chain' },
];

export default function Navbar() {
  return (
    <div className="feature-nav">
      {LINKS.map((link) => (
        <NavLink
          key={link.to}
          to={link.to}
          className={({ isActive }) => `feature-nav-link${isActive ? ' is-active' : ''}`}
        >
          {link.label}
        </NavLink>
      ))}
    </div>
  );
}
