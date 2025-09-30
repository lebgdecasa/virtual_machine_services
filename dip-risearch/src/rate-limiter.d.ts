declare class RateLimiter {
    private store;
    private maxRequests;
    private windowMs;
    constructor(maxRequests?: number, windowMs?: number);
    private getKey;
    private cleanup;
    checkLimit(key: string): {
        allowed: boolean;
        remaining: number;
        resetTime: number;
    };
    middleware(): (req: any, res: any, next: any) => void;
}
export declare const globalRateLimiter: RateLimiter;
export declare const researchRateLimiter: RateLimiter;
export {};
//# sourceMappingURL=rate-limiter.d.ts.map