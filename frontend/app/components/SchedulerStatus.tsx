import React, { useState, useEffect } from 'react'
import { Card } from './ui/card'
import { Button } from './ui/button'
import { Badge } from './ui/badge'
import { Clock, Play, Square, AlertCircle, CheckCircle, Settings } from 'lucide-react'

const API_BASE_URL = process.env.NODE_ENV === 'production' ? '' : 'http://localhost:14250'

interface SchedulerStatusData {
  scheduler_running: boolean
  enabled: boolean
  last_run: string | null
  next_run: string | null
  current_analysis_task: {
    task_id: string
    status: string
    progress: number
    message: string
  } | null
  current_news_task: {
    task_id: string
    status: string
    progress: number
    message: string
  } | null
}

export function SchedulerStatus() {
  const [status, setStatus] = useState<SchedulerStatusData | null>(null)
  const [loading, setLoading] = useState(true)
  const [stopping, setStopping] = useState(false)
  const [toggling, setToggling] = useState(false)

  const fetchStatus = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/scheduler/status`)
      if (response.ok) {
        const data = await response.json()
        setStatus(data)
      }
    } catch (error) {
      console.error('Failed to fetch scheduler status:', error)
    } finally {
      setLoading(false)
    }
  }

  const stopCurrentTask = async () => {
    setStopping(true)
    try {
      const response = await fetch(`${API_BASE_URL}/api/scheduler/stop`, { method: 'POST' })
      if (response.ok) {
        const result = await response.json()
        console.log(result.message)
        // Refresh status after a short delay
        setTimeout(fetchStatus, 1000)
      }
    } catch (error) {
      console.error('Failed to stop task:', error)
    } finally {
      setStopping(false)
    }
  }

  const toggleScheduler = async () => {
    if (!status) return
    
    setToggling(true)
    try {
      const response = await fetch(`${API_BASE_URL}/api/scheduler/enable?enabled=${!status.enabled}`, { 
        method: 'POST' 
      })
      if (response.ok) {
        const result = await response.json()
        console.log(result.message)
        // Refresh status
        fetchStatus()
      }
    } catch (error) {
      console.error('Failed to toggle scheduler:', error)
    } finally {
      setToggling(false)
    }
  }

  useEffect(() => {
    fetchStatus()
    // Refresh status every 30 seconds
    const interval = setInterval(fetchStatus, 30000)
    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return (
      <Card className="p-4">
        <div className="flex items-center space-x-2">
          <Clock className="h-5 w-5 animate-spin" />
          <span>加载调度器状态...</span>
        </div>
      </Card>
    )
  }

  if (!status) {
    return (
      <Card className="p-4">
        <div className="flex items-center space-x-2 text-red-500">
          <AlertCircle className="h-5 w-5" />
          <span>无法获取调度器状态</span>
        </div>
      </Card>
    )
  }

  const getCurrentPhase = () => {
    if (status?.current_analysis_task?.status === 'running' || status?.current_analysis_task?.status === 'pending') {
      return { text: '分析任务运行中', color: 'bg-blue-500', isRunning: true }
    }
    if (status?.current_news_task?.status === 'running' || status?.current_news_task?.status === 'pending') {
      return { text: '新闻评估运行中', color: 'bg-green-500', isRunning: true }
    }
    if (status?.current_analysis_task?.status === 'failed' || status?.current_news_task?.status === 'failed') {
      return { text: '任务失败', color: 'bg-red-500', isRunning: false }
    }
    if (status?.current_analysis_task?.status === 'cancelled' || status?.current_news_task?.status === 'cancelled') {
      return { text: '任务已取消', color: 'bg-gray-500', isRunning: false }
    }
    return { text: '空闲', color: 'bg-gray-400', isRunning: false }
  }

  const formatDateTime = (dateString: string | null) => {
    if (!dateString) return '无'
    return new Date(dateString).toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      timeZone: 'UTC',
      timeZoneName: 'short'
    })
  }

  const phaseDisplay = getCurrentPhase()
  const isTaskRunning = phaseDisplay.isRunning

  return (
    <Card className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <span className="text-sm font-medium">{status.enabled ? '调度器已启用' : '调度器已禁用'}</span>
          <Button
            size="sm"
            onClick={toggleScheduler}
            disabled={toggling}
            className="flex items-center"
          >
            <span>{toggling ? '切换中...' : (status.enabled ? '禁用' : '启用')}</span>
          </Button>
          <div className="text-sm font-medium">当前阶段:  {phaseDisplay.text} 上次运行: {formatDateTime(status.last_run)}</div>

        </div>
      </div>

      <div className="flex gap-6">
        <div className="space-y-2">
          {status.current_analysis_task && (
            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">分析任务:</span>
                <Badge variant={status.current_analysis_task.status === 'running' ? 'default' : 'secondary'}>
                  {status.current_analysis_task.status}
                </Badge>
              </div>
              {status.current_analysis_task.progress > 0 && (
                <div className="text-xs text-gray-600">
                  进度: {Math.round(status.current_analysis_task.progress * 100)}%
                </div>
              )}
              {status.current_analysis_task.message && (
                <div className="text-xs text-gray-600">
                  {status.current_analysis_task.message}
                </div>
              )}
            </div>
          )}
          
          {status.current_news_task && (
            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">新闻任务:</span>
                <Badge variant={status.current_news_task.status === 'running' ? 'default' : 'secondary'}>
                  {status.current_news_task.status}
                </Badge>
              </div>
              {status.current_news_task.progress > 0 && (
                <div className="text-xs text-gray-600">
                  进度: {Math.round(status.current_news_task.progress * 100)}%
                </div>
              )}
              {status.current_news_task.message && (
                <div className="text-xs text-gray-600">
                  {status.current_news_task.message}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {isTaskRunning && (
        <div className="flex items-center justify-between p-3 bg-blue-50 border border-blue-200 rounded">
          <div className="flex items-center space-x-2">
            <Play className="h-4 w-4 text-blue-600" />
            <span className="text-sm font-medium text-blue-800">
              定时任务正在运行中
            </span>
          </div>
          
          <Button
            variant="outline"
            size="sm"
            onClick={stopCurrentTask}
            disabled={stopping}
            className="flex items-center space-x-1"
          >
            <Square className="h-4 w-4" />
            <span>
              {stopping ? '停止中...' : '停止任务'}
            </span>
          </Button>
        </div>
      )}
    </Card>
  )
}