import React from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { Home, TrendingUp, Newspaper } from 'lucide-react'
import { cn } from '@/lib/utils'

interface NavItem {
  path: string
  label: string
  icon: React.ComponentType<{ className?: string }>
}

const navItems: NavItem[] = [
  {
    path: '/',
    label: '仪表板',
    icon: Home
  },
  {
    path: '/analysis',
    label: '分析',
    icon: TrendingUp
  },
  {
    path: '/news-evaluation',
    label: '新闻评估',
    icon: Newspaper
  }
]

export function SideNavigation() {
  const location = useLocation()

  return (
    <nav className="hidden md:flex flex-col p-2 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 border-r border-border z-50 w-24">
      <div className="flex flex-col items-center gap-2 mt-4">
        {navItems.map((item) => {
          const Icon = item.icon
          const isActive = location.pathname === item.path
          
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={cn(
                "flex flex-col items-center justify-center gap-1 p-3 rounded-lg transition-colors w-full",
                "hover:bg-accent hover:text-accent-foreground",
                isActive 
                  ? "text-primary bg-primary/10" 
                  : "text-muted-foreground"
              )}
            >
              <Icon className="h-5 w-5 shrink-0" />
              <span className="text-xs font-medium truncate">{item.label}</span>
            </NavLink>
          )
        })}
      </div>
    </nav>
  )
}
