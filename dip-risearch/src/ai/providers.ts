import { createFireworks } from '@ai-sdk/fireworks';
import { createGoogleGenerativeAI } from '@ai-sdk/google';
import { createOpenAI } from '@ai-sdk/openai';
import {
  extractReasoningMiddleware,
  LanguageModel,
  wrapLanguageModel,
} from 'ai';
import { getEncoding } from 'js-tiktoken';

import { RecursiveCharacterTextSplitter } from './text-splitter';

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
const gpt4oModel = openai?.('gpt-4o', {
  structuredOutputs: true,
});

const deepSeekR1Model = fireworks
  ? wrapLanguageModel({
      model: fireworks(
        'accounts/fireworks/models/deepseek-r1',
      ) as any,
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

export function getModel(): LanguageModel {
  // Priority order for model selection - Force Gemini if available
  if (geminiFlashModel) {
    console.log('Using Gemini Flash model (forced)');
    return geminiFlashModel;
  }

  if (customModel) {
    console.log('Using custom model:', process.env.CUSTOM_MODEL);
    return (customModel as any);
  }

  const model = deepSeekR1Model ?? gpt4oModel;

  if (!model) {
    throw new Error('No model found. Please set GEMINI_KEY, OPENAI_KEY, or FIREWORKS_KEY environment variable.');
  }

  return (model as any);
}

const MinChunkSize = 140;
const encoder = getEncoding('o200k_base');

// trim prompt to maximum context size
export function trimPrompt(
  prompt: string,
  contextSize = Number(process.env.CONTEXT_SIZE) || 128_000,
) {
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
