// 认证服务
export class AuthService {
  private static readonly AUTH_TOKEN_KEY = 'auth_token'
  private static readonly AUTH_TIME_KEY = 'auth_time'
  private static readonly USER_INFO_KEY = 'user_info'
  private static readonly SESSION_TIMEOUT = 180 * 24 * 60 * 60 * 1000 // 180天

  /**
   * 检查用户是否已认证
   */
  static isAuthenticated(): boolean {
    const token = sessionStorage.getItem(this.AUTH_TOKEN_KEY)
    const authTime = sessionStorage.getItem(this.AUTH_TIME_KEY)
    
    if (!token || !authTime) {
      return false
    }

    // 检查会话是否过期
    const now = Date.now()
    const authTimestamp = parseInt(authTime, 10)
    
    if (now - authTimestamp > this.SESSION_TIMEOUT) {
      this.clearAuth()
      return false
    }

    return !!token
  }

  /**
   * 清除认证信息
   */
  static clearAuth(): void {
    sessionStorage.removeItem(this.AUTH_TOKEN_KEY)
    sessionStorage.removeItem(this.AUTH_TIME_KEY)
    sessionStorage.removeItem(this.USER_INFO_KEY)
  }

  /**
   * 设置认证信息
   */
  static setAuth(token: string, userInfo: { name?: string; email: string }): void {
    sessionStorage.setItem(this.AUTH_TOKEN_KEY, token)
    sessionStorage.setItem(this.AUTH_TIME_KEY, Date.now().toString())
    sessionStorage.setItem(this.USER_INFO_KEY, JSON.stringify(userInfo))
  }

  /**
   * 获取当前用户信息
   */
  static getUserInfo(): { name?: string; email: string } | null {
    const userInfoStr = sessionStorage.getItem(this.USER_INFO_KEY)
    if (!userInfoStr) return null
    
    try {
      return JSON.parse(userInfoStr)
    } catch {
      return null
    }
  }

  /**
   * 用户认证（弱校验：仅需用户名和邮箱）
   */
  static async authenticate(username: string, email: string): Promise<{ success: boolean; error?: string; message?: string }> {
    try {
      // 基本输入验证
      if (!username || !username.trim()) {
        return { success: false, error: '用户名不能为空' }
      }
      
      if (!email || !email.trim()) {
        return { success: false, error: '邮箱不能为空' }
      }
      
      // 简单的邮箱格式验证
      const emailPattern = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/
      if (!emailPattern.test(email.trim())) {
        return { success: false, error: '邮箱格式不正确' }
      }

      // Use the same API base URL logic as the api service
      const { API_BASE_URL } = await import('./api')
      const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          name: username.trim(), 
          email: email.trim() 
          // 弱校验模式：不发送密码
        }),
      })

      if (response.ok) {
        const data = await response.json()
        this.setAuth(data.token || 'authenticated', { name: username.trim(), email: email.trim() })
        return { 
          success: true, 
          message: data.message || '认证成功' 
        }
      } else {
        const error = await response.json()
        return { success: false, error: error.message || '认证失败' }
      }
    } catch (error) {
      return { success: false, error: '网络错误，请重试' }
    }
  }

  /**
   * 获取剩余会话时间（毫秒）
   */
  static getRemainingSessionTime(): number {
    const authTime = sessionStorage.getItem(this.AUTH_TIME_KEY)
    if (!authTime) return 0

    const authTimestamp = parseInt(authTime, 10)
    const elapsed = Date.now() - authTimestamp
    const remaining = this.SESSION_TIMEOUT - elapsed

    return Math.max(0, remaining)
  }

  /**
   * 检查是否需要重新认证的高阶函数
   */
  static requireAuth<T extends any[]>(
    callback: (...args: T) => void | Promise<void>
  ): (...args: T) => Promise<boolean> {
    return async (...args: T): Promise<boolean> => {
      if (this.isAuthenticated()) {
        await callback(...args)
        return true
      }
      return false
    }
  }
}

// 认证状态管理Hook
export function useAuth() {
  const isAuthenticated = AuthService.isAuthenticated()
  
  const clearAuth = () => {
    AuthService.clearAuth()
  }

  const setAuth = (token: string, userInfo: { name?: string; email: string }) => {
    AuthService.setAuth(token, userInfo)
  }

  return {
    isAuthenticated,
    clearAuth,
    setAuth,
    getUserInfo: AuthService.getUserInfo,
    authenticate: AuthService.authenticate,
    getRemainingTime: AuthService.getRemainingSessionTime
  }
}