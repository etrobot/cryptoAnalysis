import React, { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { 
  Clock, 
  Play, 
  Pause, 
  RefreshCw, 
  CheckCircle, 
  XCircle, 
  AlertCircle,
  Calendar,
  TrendingUp,
  BarChart3
} from 'lucide-react'

interface TaskInfo {
  task_id?: string
  status?: string
  progress?: number
  message?: string
}

interface SchedulerStatus {
  scheduler_running: boolean
  enabled: boolean
  last_run?: string
  next_run?: string
  current_analysis_task?: TaskInfo
  current_news_task?: TaskInfo
  current_candlestick_task?: TaskInfo
  current_timeframe_review_task?: TaskInfo
}

interface TimeframeAnalysis {
  analysis_date?: string
  best_timeframe?: string
  selected_timeframes?: string[]
  trading_symbols?: string[]
  recommendation?: string
  timeframe_analysis?: Record<string, {
    avg_consecutive: number
    max_consecutive: number
    trading_score: number
    symbols_count: number
    symbols_analyzed: Array<{
      symbol: string
      green_consecutive: number
      red_consecutive: number
      max_consecutive: number
    }>
  }>
  method?: string
  completed_at?: string
  file_updated?: string
  error?: string
  message?: string
}

export function SchedulerPage() {
  const [schedulerStatus, setSchedulerStatus] = useState<SchedulerStatus | null>(null)
  const [timeframeAnalysis, setTimeframeAnalysis] = useState<TimeframeAnalysis | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchSchedulerStatus = async () => {
    try {
      const response = await fetch('/api/scheduler/status')
      if (!response.ok) throw new Error('Failed to fetch scheduler status')
      const data = await response.json()
      setSchedulerStatus(data)
    } catch (err) {
      console.error('Error fetching scheduler status:', err)
      setError('获取调度器状态失败')
    }
  }

  const fetchTimeframeAnalysis = async () => {
    try {
      const response = await fetch('/api/timeframe-analysis')
      if (!response.ok) throw new Error('Failed to fetch timeframe analysis')
      const data = await response.json()
      setTimeframeAnalysis(data)
    } catch (err) {
      console.error('Error fetching timeframe analysis:', err)
      setError('获取时间周期分析失败')
    }
  }

  const toggleScheduler = async (enabled: boolean) => {
    try {
      const response = await fetch(`/api/scheduler/enable?enabled=${enabled}`, {
        method: 'POST'
      })
      if (!response.ok) throw new Error('Failed to toggle scheduler')
      await fetchSchedulerStatus()
    } catch (err) {
      console.error('Error toggling scheduler:', err)
      setError('切换调度器状态失败')
    }
  }

  const stopCurrentTasks = async () => {
    try {
      const response = await fetch('/api/scheduler/stop', {
        method: 'POST'
      })
      if (!response.ok) throw new Error('Failed to stop tasks')
      await fetchSchedulerStatus()
    } catch (err) {
      console.error('Error stopping tasks:', err)
      setError('停止任务失败')
    }
  }

  useEffect(() => {
    const loadData = async () => {
      setLoading(true)
      await Promise.all([fetchSchedulerStatus(), fetchTimeframeAnalysis()])
      setLoading(false)
    }
    
    loadData()
    
    // 定期刷新状态
    const interval = setInterval(() => {
      fetchSchedulerStatus()
    }, 5000)
    
    return () => clearInterval(interval)
  }, [])

  const getStatusIcon = (status?: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-500" />
      case 'running':
        return <RefreshCw className="h-4 w-4 text-blue-500 animate-spin" />
      default:
        return <AlertCircle className="h-4 w-4 text-gray-400" />
    }
  }

  const getStatusBadge = (status?: string) => {
    const variants: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
      completed: "default",
      failed: "destructive", 
      running: "secondary",
      pending: "outline"
    }
    return <Badge variant={variants[status || ''] || "outline"}>{status || '未知'}</Badge>
  }

  const formatDateTime = (dateStr?: string) => {
    if (!dateStr) return '未知'
    try {
      return new Date(dateStr).toLocaleString('zh-CN')
    } catch {
      return dateStr
    }
  }

  if (loading) {
    return (
      <div className="container mx-auto p-6">
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="h-8 w-8 animate-spin" />
          <span className="ml-2">加载中...</span>
        </div>
      </div>
    )
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">定时任务管理</h1>
          <p className="text-muted-foreground">管理和监控自动化交易分析任务</p>
        </div>
        
        <div className="flex items-center gap-2">
          <Button
            variant={schedulerStatus?.enabled ? "destructive" : "default"}
            onClick={() => toggleScheduler(!schedulerStatus?.enabled)}
          >
            {schedulerStatus?.enabled ? <Pause className="h-4 w-4 mr-2" /> : <Play className="h-4 w-4 mr-2" />}
            {schedulerStatus?.enabled ? '禁用' : '启用'}定时任务
          </Button>
          
          <Button variant="outline" onClick={stopCurrentTasks}>
            <XCircle className="h-4 w-4 mr-2" />
            停止当前任务
          </Button>
          
          <Button variant="outline" onClick={() => window.location.reload()}>
            <RefreshCw className="h-4 w-4 mr-2" />
            刷新
          </Button>
        </div>
      </div>

      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-red-700">
              <XCircle className="h-4 w-4" />
              <span>{error}</span>
            </div>
          </CardContent>
        </Card>
      )}

      <Tabs defaultValue="status" className="space-y-4">
        <TabsList>
          <TabsTrigger value="status">调度器状态</TabsTrigger>
          <TabsTrigger value="timeframe">时间周期分析</TabsTrigger>
        </TabsList>

        <TabsContent value="status" className="space-y-4">
          {/* 调度器概览 */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Clock className="h-5 w-5" />
                调度器概览
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="space-y-2">
                  <p className="text-sm text-muted-foreground">运行状态</p>
                  <div className="flex items-center gap-2">
                    {schedulerStatus?.scheduler_running ? (
                      <CheckCircle className="h-4 w-4 text-green-500" />
                    ) : (
                      <XCircle className="h-4 w-4 text-red-500" />
                    )}
                    <span className="font-medium">
                      {schedulerStatus?.scheduler_running ? '运行中' : '已停止'}
                    </span>
                  </div>
                </div>
                
                <div className="space-y-2">
                  <p className="text-sm text-muted-foreground">任务启用</p>
                  <div className="flex items-center gap-2">
                    {schedulerStatus?.enabled ? (
                      <CheckCircle className="h-4 w-4 text-green-500" />
                    ) : (
                      <XCircle className="h-4 w-4 text-red-500" />
                    )}
                    <span className="font-medium">
                      {schedulerStatus?.enabled ? '已启用' : '已禁用'}
                    </span>
                  </div>
                </div>
                
                <div className="space-y-2">
                  <p className="text-sm text-muted-foreground">上次运行</p>
                  <span className="text-sm font-mono">
                    {formatDateTime(schedulerStatus?.last_run)}
                  </span>
                </div>
                
                <div className="space-y-2">
                  <p className="text-sm text-muted-foreground">下次运行</p>
                  <span className="text-sm font-mono">
                    {formatDateTime(schedulerStatus?.next_run)}
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* 当前任务 */}
          <div className="grid md:grid-cols-2 gap-4">
            {/* 分析任务 */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <TrendingUp className="h-4 w-4" />
                  分析任务
                </CardTitle>
                <CardDescription>每日加密货币分析任务</CardDescription>
              </CardHeader>
              <CardContent>
                {schedulerStatus?.current_analysis_task ? (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      {getStatusIcon(schedulerStatus.current_analysis_task.status)}
                      {getStatusBadge(schedulerStatus.current_analysis_task.status)}
                    </div>
                    
                    {schedulerStatus.current_analysis_task.progress !== undefined && (
                      <div className="space-y-2">
                        <div className="flex justify-between text-sm">
                          <span>进度</span>
                          <span>{Math.round((schedulerStatus.current_analysis_task.progress || 0) * 100)}%</span>
                        </div>
                        <Progress value={(schedulerStatus.current_analysis_task.progress || 0) * 100} />
                      </div>
                    )}
                    
                    {schedulerStatus.current_analysis_task.message && (
                      <p className="text-sm text-muted-foreground">
                        {schedulerStatus.current_analysis_task.message}
                      </p>
                    )}
                  </div>
                ) : (
                  <p className="text-muted-foreground">当前无运行任务</p>
                )}
              </CardContent>
            </Card>

            {/* 新闻任务 */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Calendar className="h-4 w-4" />
                  新闻评估任务
                </CardTitle>
                <CardDescription>每日新闻情感分析任务</CardDescription>
              </CardHeader>
              <CardContent>
                {schedulerStatus?.current_news_task ? (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      {getStatusIcon(schedulerStatus.current_news_task.status)}
                      {getStatusBadge(schedulerStatus.current_news_task.status)}
                    </div>
                    
                    {schedulerStatus.current_news_task.progress !== undefined && (
                      <div className="space-y-2">
                        <div className="flex justify-between text-sm">
                          <span>进度</span>
                          <span>{Math.round((schedulerStatus.current_news_task.progress || 0) * 100)}%</span>
                        </div>
                        <Progress value={(schedulerStatus.current_news_task.progress || 0) * 100} />
                      </div>
                    )}
                    
                    {schedulerStatus.current_news_task.message && (
                      <p className="text-sm text-muted-foreground">
                        {schedulerStatus.current_news_task.message}
                      </p>
                    )}
                  </div>
                ) : (
                  <p className="text-muted-foreground">当前无运行任务</p>
                )}
              </CardContent>
            </Card>

            {/* K线策略任务 */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BarChart3 className="h-4 w-4" />
                  K线策略任务
                </CardTitle>
                <CardDescription>每10分钟K线模式交易策略</CardDescription>
              </CardHeader>
              <CardContent>
                {schedulerStatus?.current_candlestick_task ? (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      {getStatusIcon(schedulerStatus.current_candlestick_task.status)}
                      {getStatusBadge(schedulerStatus.current_candlestick_task.status)}
                    </div>
                    
                    {schedulerStatus.current_candlestick_task.progress !== undefined && (
                      <div className="space-y-2">
                        <div className="flex justify-between text-sm">
                          <span>进度</span>
                          <span>{Math.round((schedulerStatus.current_candlestick_task.progress || 0) * 100)}%</span>
                        </div>
                        <Progress value={(schedulerStatus.current_candlestick_task.progress || 0) * 100} />
                      </div>
                    )}
                    
                    {schedulerStatus.current_candlestick_task.message && (
                      <p className="text-sm text-muted-foreground">
                        {schedulerStatus.current_candlestick_task.message}
                      </p>
                    )}
                  </div>
                ) : (
                  <p className="text-muted-foreground">当前无运行任务</p>
                )}
              </CardContent>
            </Card>

            {/* 时间周期梳理任务 */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Clock className="h-4 w-4" />
                  时间周期梳理
                </CardTitle>
                <CardDescription>每日交易时间周期分析</CardDescription>
              </CardHeader>
              <CardContent>
                {schedulerStatus?.current_timeframe_review_task ? (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      {getStatusIcon(schedulerStatus.current_timeframe_review_task.status)}
                      {getStatusBadge(schedulerStatus.current_timeframe_review_task.status)}
                    </div>
                    
                    {schedulerStatus.current_timeframe_review_task.progress !== undefined && (
                      <div className="space-y-2">
                        <div className="flex justify-between text-sm">
                          <span>进度</span>
                          <span>{Math.round((schedulerStatus.current_timeframe_review_task.progress || 0) * 100)}%</span>
                        </div>
                        <Progress value={(schedulerStatus.current_timeframe_review_task.progress || 0) * 100} />
                      </div>
                    )}
                    
                    {schedulerStatus.current_timeframe_review_task.message && (
                      <p className="text-sm text-muted-foreground">
                        {schedulerStatus.current_timeframe_review_task.message}
                      </p>
                    )}
                  </div>
                ) : (
                  <p className="text-muted-foreground">当前无运行任务</p>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="timeframe" className="space-y-4">
          {/* 时间周期分析结果 */}
          {timeframeAnalysis?.error || timeframeAnalysis?.message ? (
            <Card>
              <CardContent className="p-6">
                <div className="text-center space-y-2">
                  <AlertCircle className="h-8 w-8 mx-auto text-muted-foreground" />
                  <p className="text-muted-foreground">
                    {timeframeAnalysis.message || timeframeAnalysis.error}
                  </p>
                </div>
              </CardContent>
            </Card>
          ) : timeframeAnalysis?.timeframe_analysis ? (
            <>
              {/* 推荐结果 */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <TrendingUp className="h-5 w-5" />
                    推荐时间周期
                  </CardTitle>
                  <CardDescription>
                    基于 {timeframeAnalysis.analysis_date} 的分析结果
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center gap-4">
                    <div className="text-3xl font-bold text-primary">
                      {timeframeAnalysis.best_timeframe || '未知'}
                    </div>
                    <div className="flex-1">
                      <p className="text-muted-foreground">
                        {timeframeAnalysis.recommendation}
                      </p>
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-muted-foreground">分析方法: </span>
                      <span>{timeframeAnalysis.method || '连续K线分析'}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">更新时间: </span>
                      <span>{formatDateTime(timeframeAnalysis.completed_at)}</span>
                    </div>
                  </div>
                  
                  {/* 显示选中的时间周期和交易币种 */}
                  {timeframeAnalysis.selected_timeframes && (
                    <div className="space-y-2">
                      <div>
                        <span className="text-muted-foreground">交易时间周期: </span>
                        <div className="flex gap-1 mt-1">
                          {timeframeAnalysis.selected_timeframes.map((tf) => (
                            <Badge key={tf} variant="outline">{tf}</Badge>
                          ))}
                        </div>
                      </div>
                      
                      {timeframeAnalysis.trading_symbols && (
                        <div>
                          <span className="text-muted-foreground">交易币种: </span>
                          <div className="flex gap-1 mt-1 flex-wrap">
                            {timeframeAnalysis.trading_symbols.map((symbol) => (
                              <Badge key={symbol} variant="secondary">{symbol}</Badge>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* 详细分析结果 */}
              <Card>
                <CardHeader>
                  <CardTitle>各时间周期详细分析</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid gap-4">
                    {Object.entries(timeframeAnalysis.timeframe_analysis).map(([timeframe, stats]) => (
                      <div key={timeframe} className="border rounded-lg p-4 space-y-3">
                        <div className="flex items-center justify-between">
                          <h4 className="font-semibold">{timeframe}</h4>
                          <Badge variant={timeframe === timeframeAnalysis.best_timeframe ? "default" : "outline"}>
                            评分: {stats.trading_score.toFixed(2)}
                          </Badge>
                        </div>
                        
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                          <div>
                            <span className="text-muted-foreground">平均连续:</span>
                            <div className="font-medium">{stats.avg_consecutive.toFixed(1)}</div>
                          </div>
                          <div>
                            <span className="text-muted-foreground">最大连续:</span>
                            <div className="font-medium">{stats.max_consecutive}</div>
                          </div>
                          <div>
                            <span className="text-muted-foreground">分析币种:</span>
                            <div className="font-medium">{stats.symbols_count}</div>
                          </div>
                          <div>
                            <span className="text-muted-foreground">交易评分:</span>
                            <div className="font-medium">{stats.trading_score.toFixed(2)}</div>
                          </div>
                        </div>
                        
                        {stats.symbols_analyzed.length > 0 && (
                          <div className="space-y-2">
                            <p className="text-sm text-muted-foreground">币种详情:</p>
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                              {stats.symbols_analyzed.slice(0, 6).map((symbol) => (
                                <div key={symbol.symbol} className="text-xs bg-muted rounded p-2">
                                  <div className="font-medium">{symbol.symbol}</div>
                                  <div className="text-muted-foreground">
                                    绿:{symbol.green_consecutive} 红:{symbol.red_consecutive} 最大:{symbol.max_consecutive}
                                  </div>
                                </div>
                              ))}
                              {stats.symbols_analyzed.length > 6 && (
                                <div className="text-xs text-muted-foreground p-2">
                                  还有 {stats.symbols_analyzed.length - 6} 个币种...
                                </div>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </>
          ) : (
            <Card>
              <CardContent className="p-6">
                <div className="text-center space-y-2">
                  <Clock className="h-8 w-8 mx-auto text-muted-foreground" />
                  <p className="text-muted-foreground">暂无时间周期分析数据</p>
                  <p className="text-sm text-muted-foreground">
                    时间周期分析每日 UTC 1:00 自动运行
                  </p>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}