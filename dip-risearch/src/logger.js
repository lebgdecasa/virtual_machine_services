import * as fs from 'fs/promises';
import * as path from 'path';
export var LogLevel;
(function (LogLevel) {
    LogLevel[LogLevel["ERROR"] = 0] = "ERROR";
    LogLevel[LogLevel["WARN"] = 1] = "WARN";
    LogLevel[LogLevel["INFO"] = 2] = "INFO";
    LogLevel[LogLevel["DEBUG"] = 3] = "DEBUG";
})(LogLevel || (LogLevel = {}));
class Logger {
    logLevel;
    logFile;
    enableConsole;
    constructor() {
        this.logLevel = this.getLogLevel();
        this.logFile = process.env.LOG_FILE || path.join(process.cwd(), 'logs', 'app.log');
        this.enableConsole = process.env.NODE_ENV !== 'production';
    }
    getLogLevel() {
        const envLevel = process.env.LOG_LEVEL?.toUpperCase();
        switch (envLevel) {
            case 'ERROR': return LogLevel.ERROR;
            case 'WARN': return LogLevel.WARN;
            case 'INFO': return LogLevel.INFO;
            case 'DEBUG': return LogLevel.DEBUG;
            default: return process.env.NODE_ENV === 'production' ? LogLevel.INFO : LogLevel.DEBUG;
        }
    }
    async writeLog(entry) {
        try {
            // Ensure logs directory exists
            await fs.mkdir(path.dirname(this.logFile), { recursive: true });
            const logLine = JSON.stringify(entry) + '\n';
            await fs.appendFile(this.logFile, logLine);
        }
        catch (error) {
            console.error('Failed to write to log file:', error);
        }
    }
    shouldLog(level) {
        return level <= this.logLevel;
    }
    createLogEntry(level, message, metadata, error) {
        return {
            timestamp: new Date().toISOString(),
            level,
            message,
            metadata,
            error: error ? {
                name: error.name,
                message: error.message,
                stack: error.stack,
            } : undefined,
        };
    }
    async error(message, error, metadata) {
        if (!this.shouldLog(LogLevel.ERROR))
            return;
        const entry = this.createLogEntry('ERROR', message, metadata, error);
        if (this.enableConsole) {
            console.error(`[${entry.timestamp}] ERROR: ${message}`, error ? error.message : '', metadata || '');
        }
        await this.writeLog(entry);
    }
    async warn(message, metadata) {
        if (!this.shouldLog(LogLevel.WARN))
            return;
        const entry = this.createLogEntry('WARN', message, metadata);
        if (this.enableConsole) {
            console.warn(`[${entry.timestamp}] WARN: ${message}`, metadata || '');
        }
        await this.writeLog(entry);
    }
    async info(message, metadata) {
        if (!this.shouldLog(LogLevel.INFO))
            return;
        const entry = this.createLogEntry('INFO', message, metadata);
        if (this.enableConsole) {
            console.log(`[${entry.timestamp}] INFO: ${message}`, metadata || '');
        }
        await this.writeLog(entry);
    }
    async debug(message, metadata) {
        if (!this.shouldLog(LogLevel.DEBUG))
            return;
        const entry = this.createLogEntry('DEBUG', message, metadata);
        if (this.enableConsole) {
            console.debug(`[${entry.timestamp}] DEBUG: ${message}`, metadata || '');
        }
        await this.writeLog(entry);
    }
    // Request logging for API middleware
    async logRequest(req, res, duration) {
        const metadata = {
            method: req.method,
            url: req.url,
            statusCode: res.statusCode,
            duration: `${duration}ms`,
            ip: req.ip || req.connection?.remoteAddress,
            userAgent: req.get('User-Agent'),
        };
        if (res.statusCode >= 400) {
            await this.error(`HTTP ${res.statusCode} ${req.method} ${req.url}`, undefined, metadata);
        }
        else {
            await this.info(`HTTP ${res.statusCode} ${req.method} ${req.url}`, metadata);
        }
    }
}
export const logger = new Logger();
