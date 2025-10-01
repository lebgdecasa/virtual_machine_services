import { generateObject } from 'ai';
import { compact } from 'lodash-es';
import pLimit from 'p-limit';
import { z } from 'zod';

import { getModel, trimPrompt } from './ai/providers';
import { systemPrompt } from './prompt';

// Enhanced logging function for debugging
function log(level: 'INFO' | 'WARN' | 'ERROR' | 'DEBUG', message: string, data?: any) {
  const timestamp = new Date().toISOString();
  const prefix = `[${timestamp}] [${level}]`;

  if (data !== undefined) {
    console.log(`${prefix} ${message}`, data);
  } else {
    console.log(`${prefix} ${message}`);
  }
}

// Convenience logging functions
function logInfo(message: string, data?: any) {
  log('INFO', message, data);
}

function logWarn(message: string, data?: any) {
  log('WARN', message, data);
}

function logError(message: string, error?: any) {
  log('ERROR', message, error);
}

function logDebug(message: string, data?: any) {
  log('DEBUG', message, data);
}

// Custom API response type
type CustomSearchResult = {
  date: string;
  title: string;
  body: string;
  url: string;
  image: string;
  source: string;
  content: string;
  possible_query_used: string[];
};

type CustomSearchResponse = {
  results: CustomSearchResult[];
};

// Custom API client
class CustomSearchAPI {
  private baseUrl: string;

  constructor(baseUrl = 'http://34.71.161.89') {
    this.baseUrl = baseUrl;
    logInfo('CustomSearchAPI initialized', { baseUrl });
  }

  async search(query: string, limit: number = 5): Promise<CustomSearchResponse> {
    const startTime = Date.now();
    logInfo('Starting API search request', { query, limit, baseUrl: this.baseUrl });

    try {
      const response = await fetch(`${this.baseUrl}/search`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: [query], // API expects array of queries
          n: limit,
        }),
      });

      const duration = Date.now() - startTime;
      logInfo('API search request completed', {
        query,
        status: response.status,
        duration: `${duration}ms`
      });

      if (!response.ok) {
        logError('API request failed', {
          query,
          status: response.status,
          statusText: response.statusText,
          duration: `${duration}ms`
        });
        throw new Error(`API request failed: ${response.status} ${response.statusText}`);
      }

      const result = await response.json();
      logDebug('API search response received', {
        query,
        resultCount: result.results?.length || 0,
        duration: `${duration}ms`
      });

      return result;
    } catch (error) {
      const duration = Date.now() - startTime;
      logError('API search request error', {
        query,
        error: error instanceof Error ? error.message : String(error),
        duration: `${duration}ms`
      });
      throw error;
    }
  }
}

export type ResearchProgress = {
  currentDepth: number;
  totalDepth: number;
  currentBreadth: number;
  totalBreadth: number;
  currentQuery?: string;
  totalQueries: number;
  completedQueries: number;
};

type ResearchResult = {
  learnings: string[];
  visitedUrls: string[];
};

// increase this if you have higher API rate limits
const ConcurrencyLimit = Number(process.env.CUSTOM_API_CONCURRENCY) || 2;

// Initialize custom search API
const customSearchAPI = new CustomSearchAPI(
  process.env.CUSTOM_API_BASE_URL || 'http://34.71.161.89'
);

// take en user query, return a list of SERP queries
async function generateSerpQueries({
  query,
  numQueries = 4,
  learnings,
}: {
  query: string;
  numQueries?: number;
  // optional, if provided, the research will continue from the last learning
  learnings?: string[];
}) {
  const res = await generateObject({
    model: getModel(),
    system: systemPrompt(),
    prompt: `Given the following prompt from the user, generate a list of SERP queries to research the topic. Return a maximum of ${numQueries} queries, but feel free to return less if the original prompt is clear. Make sure each query is unique and not similar to each other: <prompt>${query}</prompt>\n\n${
      learnings
        ? `Here are some learnings from previous research, use them to generate more specific queries: ${learnings.join(
            '\n',
          )}`
        : ''
    }`,
    schema: z.object({
      queries: z
        .array(
          z.object({
            query: z.string().describe('The SERP query'),
            researchGoal: z
              .string()
              .describe(
                'First talk about the goal of the research that this query is meant to accomplish, then go deeper into how to advance the research once the results are found, mention additional research directions. Be as specific as possible, especially for additional research directions.',
              ),
          }),
        )
        .describe(`List of SERP queries, max of ${numQueries}`),
    }),
  });
  logInfo(`Generated ${res.object.queries.length} SERP queries`, {
    queryCount: res.object.queries.length,
    queries: res.object.queries.map(q => ({ query: q.query, researchGoal: q.researchGoal }))
  });

  return res.object.queries.slice(0, numQueries);
}

async function processSerpResult({
  query,
  result,
  numLearnings = 4,
  numFollowUpQuestions = 4,
}: {
  query: string;
  result: CustomSearchResponse;
  numLearnings?: number;
  numFollowUpQuestions?: number;
}) {
  // Debug log to see the actual structure
  if (result.results && result.results.length > 0) {
    logDebug(`Sample result structure for query: "${query}"`, {
      sampleResult: JSON.stringify(result.results[0], null, 2).slice(0, 500),
      totalResults: result.results.length
    });
  }

  // Extract content from custom API results
  const contents = compact(
    result.results.map((item, index) => {
      // Use the content field from the custom API
      const content = item.content || item.body || item.title;

      if (!content && Object.keys(item).length > 0) {
        logWarn(`No content found in result item ${index} for query: "${query}"`, {
          itemKeys: Object.keys(item),
          item: JSON.stringify(item, null, 2).slice(0, 300)
        });
      }

      return content;
    })
  ).map(content => trimPrompt(String(content), 25_000));

  logInfo(`Processed SERP results for query: "${query}"`, {
    totalResults: result.results.length,
    extractedContents: contents.length,
    contentLength: contents.reduce((sum, c) => sum + c.length, 0)
  });

  // If no contents found, try to use URLs for fallback
  if (contents.length === 0 && result.results.length > 0) {
    logWarn(`No content extracted for query: "${query}", attempting fallback with titles and descriptions`, {
      totalResults: result.results.length
    });
    const fallbackContents = compact(
      result.results.map((item, index) => {
        const title = item.title || '';
        const body = item.body || '';
        const url = item.url || '';
        return title || body ? `${title}\n${body}\nSource: ${url}` : null;
      })
    );

    if (fallbackContents.length > 0) {
      logInfo(`Using ${fallbackContents.length} fallback contents for query: "${query}"`, {
        fallbackCount: fallbackContents.length
      });
      contents.push(...fallbackContents.map(c => trimPrompt(c, 25_000)));
    }
  }

  // If still no contents, return empty learnings
  if (contents.length === 0) {
    logWarn(`No contents found for query: "${query}"`, {
      totalResults: result.results.length,
      resultSample: result.results.length > 0 ? JSON.stringify(result.results[0], null, 2).slice(0, 300) : 'No results'
    });
    return {
      learnings: [`Unable to extract content for query: ${query}`],
      followUpQuestions: [`Retry search with different keywords for: ${query}`],
    };
  }

  const res = await generateObject({
    model: getModel(),
    abortSignal: AbortSignal.timeout(60_000),
    system: systemPrompt(),
    prompt: trimPrompt(
      `Given the following contents from a SERP search for the query <query>${query}</query>, generate a list of learnings from the contents. Return a maximum of ${numLearnings} learnings, but feel free to return less if the contents are clear. Make sure each learning is unique and not similar to each other. The learnings should be concise and to the point, as detailed and information dense as possible. Make sure to include any entities like people, places, companies, products, things, etc in the learnings, as well as any exact metrics, numbers, or dates. The learnings will be used to research the topic further.\n\n<contents>${contents
        .map(content => `<content>\n${content}\n</content>`)
        .join('\n')}</contents>`,
    ),
    schema: z.object({
      learnings: z.array(z.string()).describe(`List of learnings, max of ${numLearnings}`),
      followUpQuestions: z
        .array(z.string())
        .describe(
          `List of follow-up questions to research the topic further, max of ${numFollowUpQuestions}`,
        ),
    }),
  });
  logInfo(`Generated ${res.object.learnings.length} learnings from SERP results`, {
    query,
    learningsCount: res.object.learnings.length,
    followUpQuestionsCount: res.object.followUpQuestions.length,
    learnings: res.object.learnings,
    followUpQuestions: res.object.followUpQuestions
  });

  return res.object;
}

export async function writeFinalReport({
  prompt,
  learnings,
  visitedUrls,
}: {
  prompt: string;
  learnings: string[];
  visitedUrls: string[];
}) {
  const startTime = Date.now();
  logInfo('Starting final report generation', {
    prompt,
    learningsCount: learnings.length,
    urlsCount: visitedUrls.length
  });

  const learningsString = learnings
    .map(learning => `<learning>\n${learning}\n</learning>`)
    .join('\n');

  logDebug('Generating report with AI model', {
    learningsStringLength: learningsString.length,
    model: 'LanguageModel'
  });

  try {
    const res = await generateObject({
      model: getModel(),
      system: systemPrompt(),
      prompt: trimPrompt(
        `Given the following prompt from the user, write a final report on the topic using the learnings from research. Make it as as detailed as possible, aim for 3 or more pages, include ALL the learnings from research:\n\n<prompt>${prompt}</prompt>\n\nHere are all the learnings from previous research:\n\n<learnings>\n${learningsString}\n</learnings>`,
      ),
      schema: z.object({
        reportMarkdown: z.string().describe('Final report on the topic in Markdown'),
      }),
    });

    const duration = Date.now() - startTime;
    const reportLength = res.object.reportMarkdown.length;

    logInfo('Final report generated successfully', {
      duration: `${duration}ms`,
      reportLength,
      urlsIncluded: visitedUrls.length
    });

    // Append the visited URLs section to the report
    const urlsSection = `\n\n## Sources\n\n${visitedUrls.map(url => `- ${url}`).join('\n')}`;
    const finalReport = res.object.reportMarkdown + urlsSection;

    logDebug('Report generation completed', {
      finalReportLength: finalReport.length,
      urlsSectionLength: urlsSection.length
    });

    return finalReport;
  } catch (error) {
    const duration = Date.now() - startTime;
    logError('Error generating final report', {
      prompt,
      error: error instanceof Error ? error.message : String(error),
      duration: `${duration}ms`,
      stack: error instanceof Error ? error.stack : undefined
    });
    throw error;
  }
}

export async function writeFinalAnswer({
  prompt,
  learnings,
}: {
  prompt: string;
  learnings: string[];
}) {
  const startTime = Date.now();
  logInfo('Starting final answer generation', {
    prompt,
    learningsCount: learnings.length
  });

  const learningsString = learnings
    .map(learning => `<learning>\n${learning}\n</learning>`)
    .join('\n');

  logDebug('Generating answer with AI model', {
    learningsStringLength: learningsString.length,
    model: 'LanguageModel'
  });

  try {
    const res = await generateObject({
      model: getModel(),
      system: systemPrompt(),
      prompt: trimPrompt(
        `Given the following prompt from the user, write a final answer on the topic using the learnings from research. Follow the format specified in the prompt. Do not yap or babble or include any other text than the answer besides the format specified in the prompt. Keep the answer as concise as possible - usually it should be just a few words or maximum a sentence. Try to follow the format specified in the prompt (for example, if the prompt is using Latex, the answer should be in Latex. If the prompt gives multiple answer choices, the answer should be one of the choices).\n\n<prompt>${prompt}</prompt>\n\nHere are all the learnings from research on the topic that you can use to help answer the prompt:\n\n<learnings>\n${learningsString}\n</learnings>`,
      ),
      schema: z.object({
        exactAnswer: z
          .string()
          .describe('The final answer, make it short and concise, just the answer, no other text'),
      }),
    });

    const duration = Date.now() - startTime;
    const answerLength = res.object.exactAnswer.length;

    logInfo('Final answer generated successfully', {
      duration: `${duration}ms`,
      answerLength,
      answerPreview: res.object.exactAnswer.slice(0, 100) + (res.object.exactAnswer.length > 100 ? '...' : '')
    });

    return res.object.exactAnswer;
  } catch (error) {
    const duration = Date.now() - startTime;
    logError('Error generating final answer', {
      prompt,
      error: error instanceof Error ? error.message : String(error),
      duration: `${duration}ms`,
      stack: error instanceof Error ? error.stack : undefined
    });
    throw error;
  }
}

export async function deepResearch({
  query,
  breadth,
  depth,
  learnings = [],
  visitedUrls = [],
  onProgress,
}: {
  query: string;
  breadth: number;
  depth: number;
  learnings?: string[];
  visitedUrls?: string[];
  onProgress?: (progress: ResearchProgress) => void;
}): Promise<ResearchResult> {
  const startTime = Date.now();
  logInfo('Starting deep research', {
    query,
    breadth,
    depth,
    existingLearningsCount: learnings.length,
    existingUrlsCount: visitedUrls.length
  });

  const progress: ResearchProgress = {
    currentDepth: depth,
    totalDepth: depth,
    currentBreadth: breadth,
    totalBreadth: breadth,
    totalQueries: 0,
    completedQueries: 0,
  };

  const reportProgress = (update: Partial<ResearchProgress>) => {
    Object.assign(progress, update);
    logDebug('Research progress update', { progress: { ...progress, ...update } });
    onProgress?.(progress);
  };

  logInfo('Generating SERP queries', { query, breadth });
  const serpQueries = await generateSerpQueries({
    query,
    learnings,
    numQueries: breadth,
  });

  logInfo('SERP queries generated', {
    query,
    queriesCount: serpQueries.length,
    queries: serpQueries.map(q => q.query)
  });

  reportProgress({
    totalQueries: serpQueries.length,
    currentQuery: serpQueries[0]?.query,
  });

  const limit = pLimit(ConcurrencyLimit);

  logInfo('Starting parallel search execution', {
    query,
    concurrencyLimit: ConcurrencyLimit,
    queriesCount: serpQueries.length
  });

  const results = await Promise.all(
    serpQueries.map((serpQuery, index) =>
      limit(async () => {
        const queryStartTime = Date.now();
        logInfo(`Executing search ${index + 1}/${serpQueries.length}`, {
          query: serpQuery.query,
          researchGoal: serpQuery.researchGoal
        });

        try {
          const result = await customSearchAPI.search(serpQuery.query, 5);

          const queryDuration = Date.now() - queryStartTime;
          logInfo(`Search completed for query ${index + 1}`, {
            query: serpQuery.query,
            resultsCount: result.results?.length || 0,
            duration: `${queryDuration}ms`
          });

          // Collect URLs from this search
          const newUrls = compact(result.results.map(item => item.url));
          const newBreadth = Math.ceil(breadth / 2);
          const newDepth = depth - 1;

          logDebug('Processing SERP results', {
            query: serpQuery.query,
            newUrlsCount: newUrls.length,
            newBreadth,
            newDepth
          });

          const newLearnings = await processSerpResult({
            query: serpQuery.query,
            result,
            numFollowUpQuestions: newBreadth,
          });
          const allLearnings = [...learnings, ...newLearnings.learnings];
          const allUrls = [...visitedUrls, ...newUrls];

          if (newDepth > 0) {
            logInfo(`Researching deeper for query ${index + 1}`, {
              query: serpQuery.query,
              newBreadth,
              newDepth,
              newLearningsCount: newLearnings.learnings.length,
              followUpQuestionsCount: newLearnings.followUpQuestions.length
            });

            reportProgress({
              currentDepth: newDepth,
              currentBreadth: newBreadth,
              completedQueries: progress.completedQueries + 1,
              currentQuery: serpQuery.query,
            });

            const nextQuery = `
            Previous research goal: ${serpQuery.researchGoal}
            Follow-up research directions: ${newLearnings.followUpQuestions.map(q => `\n${q}`).join('')}
          `.trim();

            logDebug('Recursive research call', {
              nextQuery: nextQuery.slice(0, 200) + '...',
              newBreadth,
              newDepth
            });

            return deepResearch({
              query: nextQuery,
              breadth: newBreadth,
              depth: newDepth,
              learnings: allLearnings,
              visitedUrls: allUrls,
              onProgress,
            });
          } else {
            logInfo(`Reached maximum depth for query ${index + 1}`, {
              query: serpQuery.query,
              finalLearningsCount: allLearnings.length,
              finalUrlsCount: allUrls.length
            });

            reportProgress({
              currentDepth: 0,
              completedQueries: progress.completedQueries + 1,
              currentQuery: serpQuery.query,
            });
            return {
              learnings: allLearnings,
              visitedUrls: allUrls,
            };
          }
        } catch (e: any) {
          const queryDuration = Date.now() - queryStartTime;
          if (e.message && e.message.includes('Timeout')) {
            logError(`Timeout error for query ${index + 1}`, {
              query: serpQuery.query,
              error: e.message,
              duration: `${queryDuration}ms`,
              stack: e.stack
            });
          } else {
            logError(`Error executing query ${index + 1}`, {
              query: serpQuery.query,
              error: e.message,
              duration: `${queryDuration}ms`,
              stack: e.stack
            });
          }
          return {
            learnings: [],
            visitedUrls: [],
          };
        }
      }),
    ),
  );

  const finalLearnings = [...new Set(results.flatMap(r => r.learnings))];
  const finalUrls = [...new Set(results.flatMap(r => r.visitedUrls))];
  const totalDuration = Date.now() - startTime;

  logInfo('Deep research completed', {
    query,
    totalDuration: `${totalDuration}ms`,
    finalLearningsCount: finalLearnings.length,
    finalUrlsCount: finalUrls.length,
    queriesExecuted: results.length
  });

  return {
    learnings: finalLearnings,
    visitedUrls: finalUrls,
  };
}
