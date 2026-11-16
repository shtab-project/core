import { Navigate, createBrowserRouter } from 'react-router'
import App from '../App.tsx'
import { ProfilePage } from '../pages/ProfilePage.tsx'
import { UsersPage } from '../pages/UsersPage.tsx'
import { PluginPage } from '../pages/PluginPage.tsx'
import { PluginCatalogPage } from '../pages/PluginCatalogPage.tsx'

export const router = createBrowserRouter([
  {
    path: '/',
    Component: App,
    children: [
      { index: true, element: <Navigate to="/profile" replace /> },
      { path: 'profile', Component: ProfilePage },
      { path: 'users', Component: UsersPage },
      { path: 'plugins', Component: PluginCatalogPage },
      { path: '*', Component: PluginPage },
    ],
  },
])
