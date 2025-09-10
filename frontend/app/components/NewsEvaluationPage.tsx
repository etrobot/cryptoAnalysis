import { useState, useEffect, useCallback } from 'react'
import { Play, Square, RefreshCw, TrendingUp, Newspaper, AlertCircle, CheckCircle } from 'lucide-react'
import { Button } from './ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card'
import { Progress } from './ui/progress'
import { Badge } from './ui/badge'
import { api, createTaskStatusPoller } from '../services/api'
import { NewsTaskResult, NewsEvaluationResult, TaskStatus } from '../types'
import { useIsMobile } from '../hooks/use-mobile'

export function NewsEvaluationPage() {
  const [currentTask, setCurrentTask] = useState<NewsTaskResult | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [latestResults, setLatestResults] = useState<NewsTaskResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [stopPoller, setStopPoller] = useState<(() => void) | null>(null)
  
  const isMobile = useIsMobile()

  // Configuration state
  const [topN, setTopN] = useState(10)
  const [newsPerSymbol, setNewsPerSymbol] = useState(3)
  const [openaiModel] = useState("gpt-3.5-turbo")

  const loadLatestResults = useCallback(async () => {
    try {
      const results = await api.getLatestNewsResults()
      setLatestResults(results)
    } catch (err) {
      console.error('Failed to load latest results:', err)
    }
  }, [])

  useEffect(() => {
    loadLatestResults()
  }, [loadLatestResults])

  const startNewsEvaluation = async () => {
    try {
      setIsLoading(true)
      setError(null)
      
      const response = await api.startNewsEvaluation(topN, newsPerSymbol, openaiModel)
      
      const initialTask: NewsTaskResult = {
        task_id: response.task_id,
        status: response.status,
        progress: 0,
        message: response.message,
        created_at: new Date().toISOString()
      }
      
      setCurrentTask(initialTask)
      
      // Start polling for updates
      const poller = createTaskStatusPoller(
        response.task_id,
        (task) => {
          setCurrentTask({
            ...task,
            result: task.data ? { data: task.data } as any : undefined
          } as NewsTaskResult)
        },
        (task) => {
          setCurrentTask({
            ...task,
            result: task.data ? { data: task.data } as any : undefined
          } as NewsTaskResult)
          setIsLoading(false)
          loadLatestResults()
        },
        (error) => {
          setError(error)
          setIsLoading(false)
        }
      )
      
      setStopPoller(() => poller)
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
      setIsLoading(false)
    }
  }

  const stopNewsEvaluation = async () => {
    if (!currentTask) return
    
    try {
      await api.stopNewsTask(currentTask.task_id)
      if (stopPoller) {
        stopPoller()
        setStopPoller(null)
      }
      setIsLoading(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to stop task')
    }
  }

  const getStatusIcon = (status: TaskStatus) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-600" />
      case 'failed':
        return <AlertCircle className="h-4 w-4 text-red-600" />
      case 'running':
        return <RefreshCw className="h-4 w-4 text-blue-600 animate-spin" />
      default:
        return null
    }
  }

  const getScoreColor = (score: number) => {
    if (score >= 4) return 'bg-green-500'
    if (score >= 3) return 'bg-yellow-500'
    if (score >= 2) return 'bg-orange-500'
    return 'bg-red-500'
  }

  return (
    <div className={`min-h-screen bg-background ${isMobile ? 'p-4 pb-20' : 'p-8'}`}>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center gap-3">
          <Newspaper className="h-8 w-8 text-primary" />
          <div>
            <h1 className="text-2xl font-bold">新闻评估</h1>
            <p className="text-muted-foreground">基于成交额Top币种的新闻内容进行AI评估</p>
          </div>
        </div>

        {/* Control Panel */}
        <Card>
          <CardHeader>
            <CardTitle>评估配置</CardTitle>
            <CardDescription>
              配置新闻评估参数并启动分析任务
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium">成交额Top币种数量</label>
                <select 
                  value={topN} 
                  onChange={(e) => setTopN(Number(e.target.value))}
                  className="w-full mt-1 p-2 border rounded-md"
                  disabled={isLoading}
                >
                  <option value={5}>Top 5</option>
                  <option value={10}>Top 10</option>
                  <option value={20}>Top 20</option>
                </select>
              </div>
              <div>
                <label className="text-sm font-medium">每个币种新闻数量</label>
                <select 
                  value={newsPerSymbol} 
                  onChange={(e) => setNewsPerSymbol(Number(e.target.value))}
                  className="w-full mt-1 p-2 border rounded-md"
                  disabled={isLoading}
                >
                  <option value={1}>1条</option>
                  <option value={3}>3条</option>
                  <option value={5}>5条</option>
                </select>
              </div>
            </div>
            
            <div className="flex gap-2">
              <Button 
                onClick={startNewsEvaluation} 
                disabled={isLoading}
                className="flex items-center gap-2"
              >
                <Play className="h-4 w-4" />
                开始评估
              </Button>
              
              {isLoading && (
                <Button 
                  onClick={stopNewsEvaluation} 
                  variant="outline"
                  className="flex items-center gap-2"
                >
                  <Square className="h-4 w-4" />
                  停止
                </Button>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Current Task Status */}
        {currentTask && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                {getStatusIcon(currentTask.status)}
                任务状态
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <div className="flex justify-between text-sm mb-2">
                  <span>{currentTask.message}</span>
                  <span>{Math.round(currentTask.progress * 100)}%</span>
                </div>
                <Progress value={currentTask.progress * 100} />
              </div>
              
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="font-medium">任务ID:</span> {currentTask.task_id}
                </div>
                <div>
                  <span className="font-medium">状态:</span>
                  <Badge variant={currentTask.status === 'completed' ? 'default' : 'secondary'} className="ml-2">
                    {currentTask.status}
                  </Badge>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Error Display */}
        {error && (
          <Card className="border-red-200 bg-red-50">
            <CardContent className="pt-6">
              <div className="flex items-center gap-2 text-red-600">
                <AlertCircle className="h-4 w-4" />
                <span className="font-medium">错误:</span>
                <span>{error}</span>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Latest Results */}
        {latestResults?.result && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="h-5 w-5" />
                最新评估结果
              </CardTitle>
              <CardDescription>
                共评估 {latestResults.result.summary.total_symbols} 个币种，
                {latestResults.result.summary.total_news} 条新闻，
                平均评分: {latestResults.result.summary.average_score.toFixed(1)}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4">
                {latestResults.result.data.map((result: NewsEvaluationResult) => (
                  <div key={result.symbol} className="border rounded-lg p-4">
                    <div className="flex items-center justify-between mb-2">
                      <div>
                        <h3 className="font-semibold text-lg">{result.base_coin}</h3>
                        <p className="text-sm text-muted-foreground">
                          {result.news_count} 条新闻
                        </p>
                      </div>
                      <div className="text-right">
                        <div className="flex items-center gap-2">
                          <div 
                            className={`w-3 h-3 rounded-full ${getScoreColor(result.evaluation.overall_score)}`}
                          />
                          <span className="text-2xl font-bold">
                            {result.evaluation.overall_score.toFixed(1)}
                          </span>
                        </div>
                        <p className="text-xs text-muted-foreground">
                          最高: {result.evaluation.top_scoring_criterion}
                        </p>
                      </div>
                    </div>
                    
                    <div className="mt-3">
                      <p className="text-sm text-muted-foreground">
                        {result.news_summary}
                      </p>
                    </div>
                    
                    {result.error && (
                      <div className="mt-2 text-sm text-red-600 flex items-center gap-1">
                        <AlertCircle className="h-3 w-3" />
                        {result.error}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}