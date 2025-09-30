import { createFireworks } from '@ai-sdk/fireworks';
import { createGoogleGenerativeAI } from '@ai-sdk/google';
import { createOpenAI } from '@ai-sdk/openai';
import { extractReasoningMiddleware, wrapLanguageModel, } from 'ai';
import { getEncoding } from 'js-tiktoken';
import { RecursiveCharacterTextSplitter } from './text-splitter';
import { logger } from '../logger';
// Providers
const openai = process.env.OPENAI_KEY
    ? createOpenAI({
        apiKey: process.env.OPENAI_KEY,
        baseURL: process.env.OPENAI_ENDPOINT || 'https://api.openai.com/v1',
    })
    : undefined;
const fireworks = process.env.FIREWORKS_KEY
    ? createFireworks({
        apiKey: process.env.FIREWORKS_KEY,
    })
    : undefined;
// Models
const o3MiniModel = openai?.('o3-mini', {
    reasoningEffort: 'medium',
    structuredOutputs: true,
});
const deepSeekR1Model = fireworks
    ? wrapLanguageModel({
        model: fireworks('accounts/fireworks/models/deepseek-r1'),
        middleware: extractReasoningMiddleware({ tagName: 'think' }),
    })
    : undefined;
// Google Gemini provider
const googleProvider = process.env.GEMINI_KEY
    ? createGoogleGenerativeAI({
        apiKey: process.env.GEMINI_KEY,
    })
    : undefined;
// Google Gemini model
const geminiFlashModel = googleProvider?.('gemini-2.5-flash');
// Custom model configuration
const customModel = process.env.CUSTOM_MODEL && openai
    ? openai(process.env.CUSTOM_MODEL, {
        structuredOutputs: true,
    })
    : undefined;
// Model cache to avoid recreating models
let modelCache = null;
let lastModelConfig = null;
function getModelConfigHash() {
    return JSON.stringify({
        customModel: process.env.CUSTOM_MODEL,
        useGemini: process.env.USE_GEMINI,
        openaiKey: !!process.env.OPENAI_KEY,
        fireworksKey: !!process.env.FIREWORKS_KEY,
        geminiKey: !!process.env.GEMINI_KEY,
    });
}
export function getModel() {
    const configHash = getModelConfigHash();
    // Return cached model if configuration hasn't changed
    if (modelCache && lastModelConfig === configHash) {
        return modelCache;
    }
    let selectedModel = null;
    try {
        // Priority order for model selection
        if (customModel) {
            logger.info('Using custom model', { model: process.env.CUSTOM_MODEL });
            selectedModel = customModel;
        }
        else if (geminiFlashModel && process.env.USE_GEMINI === 'true') {
            logger.info('Using Gemini Flash model');
            selectedModel = geminiFlashModel;
        }
        else {
            // Try DeepSeek R1 first, then o3-mini, then fallback to Gemini
            selectedModel = (deepSeekR1Model ?? o3MiniModel ?? geminiFlashModel) || null;
        }
        if (!selectedModel) {
            throw new Error('No AI model available. Please configure at least one of: OPENAI_KEY, FIREWORKS_KEY, GEMINI_KEY, or CUSTOM_MODEL');
        }
        // Cache the model
        modelCache = selectedModel;
        lastModelConfig = configHash;
        logger.info('AI model initialized', {
            modelId: selectedModel.modelId || 'unknown',
            provider: selectedModel.constructor.name,
        });
        return selectedModel;
    }
    catch (error) {
        logger.error('Failed to initialize AI model', error);
        throw error;
    }
}
// Function to clear model cache (useful for testing or config changes)
export function clearModelCache() {
    modelCache = null;
    lastModelConfig = null;
    logger.debug('Model cache cleared');
}
const MinChunkSize = 140;
const encoder = getEncoding('o200k_base');
// trim prompt to maximum context size
export function trimPrompt(prompt, contextSize = Number(process.env.CONTEXT_SIZE) || 128_000) {
    if (!prompt) {
        return '';
    }
    const length = encoder.encode(prompt).length;
    if (length <= contextSize) {
        return prompt;
    }
    const overflowTokens = length - contextSize;
    // on average it's 3 characters per token, so multiply by 3 to get a rough estimate of the number of characters
    const chunkSize = prompt.length - overflowTokens * 3;
    if (chunkSize < MinChunkSize) {
        return prompt.slice(0, MinChunkSize);
    }
    const splitter = new RecursiveCharacterTextSplitter({
        chunkSize,
        chunkOverlap: 0,
    });
    const trimmedPrompt = splitter.splitText(prompt)[0] ?? '';
    // last catch, there's a chance that the trimmed prompt is same length as the original prompt, due to how tokens are split & innerworkings of the splitter, handle this case by just doing a hard cut
    if (trimmedPrompt.length === prompt.length) {
        return trimPrompt(prompt.slice(0, chunkSize), contextSize);
    }
    // recursively trim until the prompt is within the context size
    return trimPrompt(trimmedPrompt, contextSize);
}
