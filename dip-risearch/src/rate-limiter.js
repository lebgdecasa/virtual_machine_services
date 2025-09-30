class RateLimiter {
    store = new Map();
    maxRequests;
    windowMs;
    constructor(maxRequests = 100, windowMs = 15 * 60 * 1000) {
        this.maxRequests = maxRequests;
        this.windowMs = windowMs;
        // Clean up expired entries every 5 minutes
        setInterval(() => this.cleanup(), 5 * 60 * 1000);
    }
    getKey(ip, endpoint) {
        return endpoint ? `${ip}:${endpoint}` : ip;
    }
    cleanup() {
        const now = Date.now();
        for (const [key, entry] of this.store.entries()) {
            if (now > entry.resetTime) {
                this.store.delete(key);
            }
        }
    }
    checkLimit(key) {
        const now = Date.now();
        const entry = this.store.get(key);
        if (!entry || now > entry.resetTime) {
            // First request or window expired
            const resetTime = now + this.windowMs;
            this.store.set(key, { count: 1, resetTime });
            return {
                allowed: true,
                remaining: this.maxRequests - 1,
                resetTime,
            };
        }
        if (entry.count >= this.maxRequests) {
            return {
                allowed: false,
                remaining: 0,
                resetTime: entry.resetTime,
            };
        }
        // Increment count
        entry.count++;
        this.store.set(key, entry);
        return {
            allowed: true,
            remaining: this.maxRequests - entry.count,
            resetTime: entry.resetTime,
        };
    }
    middleware() {
        return (req, res, next) => {
            const ip = req.ip || req.connection?.remoteAddress || 'unknown';
            const endpoint = req.path;
            const key = this.getKey(ip, endpoint);
            const result = this.checkLimit(key);
            // Add rate limit headers
            res.set({
                'X-RateLimit-Limit': this.maxRequests,
                'X-RateLimit-Remaining': result.remaining,
                'X-RateLimit-Reset': Math.floor(result.resetTime / 1000),
            });
            if (!result.allowed) {
                res.status(429).json({
                    error: 'Too Many Requests',
                    message: `Rate limit exceeded. Try again after ${Math.ceil((result.resetTime - Date.now()) / 1000)} seconds.`,
                    retryAfter: Math.ceil((result.resetTime - Date.now()) / 1000),
                });
                return;
            }
            next();
        };
    }
}
// Global rate limiter instances
export const globalRateLimiter = new RateLimiter(Number(process.env.RATE_LIMIT_MAX_REQUESTS) || 100, Number(process.env.RATE_LIMIT_WINDOW_MS) || 15 * 60 * 1000);
export const researchRateLimiter = new RateLimiter(Number(process.env.RESEARCH_RATE_LIMIT_MAX_REQUESTS) || 10, Number(process.env.RESEARCH_RATE_LIMIT_WINDOW_MS) || 60 * 60 * 1000 // 1 hour
);
