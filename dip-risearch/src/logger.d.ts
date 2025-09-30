export declare enum LogLevel {
    ERROR = 0,
    WARN = 1,
    INFO = 2,
    DEBUG = 3
}
export interface LogEntry {
    timestamp: string;
    level: string;
    message: string;
    metadata?: Record<string, any>;
    error?: {
        name: string;
        message: string;
        stack?: string;
    };
}
declare class Logger {
    private logLevel;
    private logFile;
    private enableConsole;
    constructor();
    private getLogLevel;
    private writeLog;
    private shouldLog;
    private createLogEntry;
    error(message: string, error?: Error, metadata?: Record<string, any>): Promise<void>;
    warn(message: string, metadata?: Record<string, any>): Promise<void>;
    info(message: string, metadata?: Record<string, any>): Promise<void>;
    debug(message: string, metadata?: Record<string, any>): Promise<void>;
    logRequest(req: any, res: any, duration: number): Promise<void>;
}
export declare const logger: Logger;
export {};
//# sourceMappingURL=logger.d.ts.map