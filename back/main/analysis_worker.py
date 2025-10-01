# back/main/analysis_worker.py
import actions.generate_project_overview
import actions.scrape_and_filter_posts
import actions.generate_analysis
import actions.call_deep_research_api
import actions.generate_personas_json
import actions.gemini_api
import actions.markdown_to_json
import actions.generate_project_overview
import time
import random
import actions.create_personas
import asyncio
import traceback
import os
import json
import logging
from dotenv import load_dotenv
import os
from supabase_client import supabase
from datetime import datetime
from actions.send_email import send_project_ready_email

# Load environment variables from the .env file in the project root
# Get the project root directory (2 levels up from this file)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path)
api_key = os.getenv("NEXT_PUBLIC_GEMINI_API_KEY")
BASE_DATA_DIR = "task_data"

# Enhanced logging system for debugging
class AnalysisLogger:
    """Enhanced logging system for analysis worker debugging"""

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.logger = logging.getLogger(f"analysis_worker.{task_id}")
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                f'[%(asctime)s] [%(levelname)s] [TASK:{task_id}] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.DEBUG)

    def info(self, message: str, extra_data: dict = None):
        """Log info message with optional extra data"""
        if extra_data:
            self.logger.info(f"{message} | {extra_data}")
        else:
            self.logger.info(message)

    def warn(self, message: str, extra_data: dict = None):
        """Log warning message with optional extra data"""
        if extra_data:
            self.logger.warning(f"{message} | {extra_data}")
        else:
            self.logger.warning(message)

    def error(self, message: str, error: Exception = None, extra_data: dict = None):
        """Log error message with optional exception and extra data"""
        data = {}
        if error:
            data['error'] = str(error)
            data['error_type'] = type(error).__name__
        if extra_data:
            data.update(extra_data)
        self.logger.error(f"{message} | {data}")

    def debug(self, message: str, extra_data: dict = None):
        """Log debug message with optional extra data"""
        if extra_data:
            self.logger.debug(f"{message} | {extra_data}")
        else:
            self.logger.debug(message)

    def timing(self, step_name: str, duration: float, extra_data: dict = None):
        """Log timing information for a step"""
        data = {
            'duration_seconds': round(duration, 2),
            'duration_minutes': round(duration / 60, 1)
        }
        if extra_data:
            data.update(extra_data)
        self.logger.info(f"[TIMING] {step_name} completed in {data['duration_seconds']}s | {data}")

# Define the main analysis function
def run_analysis_job(product_description: str, task_id: str, project_id: str, name: str, update_status_callback, log_callback, loop: asyncio.AbstractEventLoop):
    """
    Runs the full analysis pipeline as a background job with comprehensive file saving.

    This function performs a complete netnographic analysis pipeline including:
    1. Key trends analysis via deep research API
    2. Reddit subreddit discovery and filtering
    3. Post scraping and LLM-based filtering
    4. Multi-stage analysis (JTBD, Pains, Gains, Recap)
    5. Final synthesis and persona generation

    All major analysis outputs are automatically saved as markdown files in the task directory:
    - key_trends_report_{task_id}.md: Deep research trends analysis
    - jtbd_analysis_{task_id}.md: Jobs-to-be-Done analysis
    - pains_analysis_{task_id}.md: User pains and frustrations analysis
    - gains_analysis_{task_id}.md: User gains and desired outcomes analysis
    - recap_analysis_{task_id}.md: Ranked summary of Jobs, Pains, and Gains
    - analysis_final_{task_id}.md: Comprehensive synthesis report

    Additional data files saved:
    - persona_details_{task_id}.json: Generated persona data and prompts
    - timing_report_{task_id}.json: Detailed timing breakdown

    Args:
        product_description: The product description input by the user.
        task_id: The unique ID for this task.
        update_status_callback: A function to call to update the task's overall status and data.
                                 Expected signature: update_status_callback(task_id, status=None, data_key=None, data_value=None)
        log_callback: A function to call to send log messages.
                      Expected signature: log_callback(task_id, message)
        loop: The asyncio event loop for handling async callbacks.
    """
    # Initialize enhanced logging system
    logger = AnalysisLogger(task_id)

    # Start overall timing
    overall_start_time = time.time()
    step_timings = {}

    def log_step_time(step_name, start_time, extra_data=None):
        """Helper to log and store step timing."""
        elapsed = time.time() - start_time
        step_timings[step_name] = elapsed
        elapsed_str = f"{elapsed:.2f}s"

        # Use enhanced logging
        logger.timing(step_name, elapsed, extra_data)

        # Keep original callback for UI updates
        safe_callback(lambda: log_callback(task_id, f"⏱️ {step_name} completed in {elapsed_str}"))
        print(f"[TIMING] {step_name}: {elapsed_str}")

    final_analysis_result = None

    # Log job initialization
    logger.info("Analysis job started", {
        'product_description_length': len(product_description),
        'task_id': task_id,
        'project_id': project_id,
        'product_name': name
    })


    task_dir = os.path.join(BASE_DATA_DIR, task_id)
    logger.info("Setting up task directories", {'task_dir': task_dir})

    try:
        os.makedirs(task_dir, exist_ok=True)
        # Create subdirectory for scraped posts as well
        scraped_dir = os.path.join(task_dir, "scraped_subreddits")
        os.makedirs(scraped_dir, exist_ok=True)
        logger.info("Task directories created successfully", {
            'task_dir': task_dir,
            'scraped_dir': scraped_dir
        })
        print(f"Ensured task directory exists: {task_dir}")
    except OSError as e:
        # Handle potential error during directory creation
        error_message = f"CRITICAL ERROR: Could not create task directory {task_dir}. Error: {e}"
        logger.error("Failed to create task directories", e, {'task_dir': task_dir})
        print(error_message)
        safe_callback(lambda: log_callback(task_id, error_message))
        safe_callback(lambda: update_status_callback(task_id, status="failed", data_key="error", data_value=error_message))
        return # Stop execution if directory cannot be created

    def safe_callback(callback_func):
        """Helper to run callback function safely."""
        try:
            # Check if the callback_func is already a coroutine object
            if asyncio.iscoroutine(callback_func):
                # If it's a coroutine object, run it directly
                future = asyncio.run_coroutine_threadsafe(callback_func, loop)
                pass
            # Check if the callback is a coroutine function
            elif asyncio.iscoroutinefunction(callback_func):
                # If it's an async function, call it first to get the coroutine, then run it
                coro = callback_func()
                future = asyncio.run_coroutine_threadsafe(coro, loop)
                pass
            else:
                # Check if callback_func is a lambda that returns a coroutine
                try:
                    result = callback_func()
                    if asyncio.iscoroutine(result):
                        # If calling the function returns a coroutine, run it
                        future = asyncio.run_coroutine_threadsafe(result, loop)
                        pass
                    # If it's a regular function that doesn't return a coroutine, we're done
                except Exception as e:
                    print(f"Error calling callback for task {task_id}: {e}")
        except Exception as e:
            # Log errors happening during callback execution
            print(f"Error running callback for task {task_id}: {e}")

    try:
        ## Create a deepresearch (Key Trends) ##
        step_start = time.time()
        logger.info("Starting Key Trends Analysis")
        safe_callback(lambda: log_callback(task_id, "Starting Key Trends Analysis..."))
        safe_callback(lambda: update_status_callback(task_id, status="running_key_trends"))

        key_trend_prompt_generator = f'''
        I need you to adapt the following generic prompt to the project description. Do not output anything else but the modified prompt.
        You must not add anything else to the adapted prompt.
        Here is the original prompt:
        ---
        {name} is a {product_description}, not yet launched.
        Please conduct a broad netnography analysis by exploring social media, online forums, subreddits, blogs, and other relevant digital channels to identify emerging trends, user sentiments, pain points, and competitive benchmarks in the {name} domain.
        The goal is to understand current market conditions, uncover user expectations, and gather insights from diverse demographics and regions so that {name} can effectively refine its value proposition and strategy before launch.
        As part of this study, please discover and examine any existing platforms or solutions that may be considered competitors, and provide a synthesized report on how {name} can uniquely position itself based on your findings.
        ---
        here is the project description:
        ---
        {product_description}
        ---

        Remember, you must only output the modified prompt.
        '''

        logger.debug("Preparing key trends prompt", {
            'prompt_length': len(key_trend_prompt_generator),
            'product_name': name,
            'product_description_length': len(product_description)
        })

        print(f"TASK {task_id}: ----> BEFORE gemini_api.generate <----")
        ## key_trend_prompt = back.actions.gemini_api.generate(key_trend_prompt_generator)
        key_trend_prompt = f'''PRODUCT_NAME: {name}
                              PRODUCT_DESCRIPTION: {product_description}
                                Focus on uncovering:
                                - Non-obvious indirect competitors and substitutes
                                - Trends in hydration tech and consumer health gadgets
                                - Strategic GTM insights that could create defensibility
                                - Any overlooked buyer segments worth exploring
                                '''
        print(f"TASK {task_id}: ----> AFTER gemini_api.generate <----")

        logger.debug("Key trends prompt prepared", {
            'prompt_length': len(key_trend_prompt)
        })

        logger.info("Starting deep research API call", {
            'prompt_length': len(key_trend_prompt),
            'breadth': 4,
            'depth': 3
        })

        print(f"TASK {task_id}: ----> BEFORE call_deep_research_api.run_research_api <----")

        report = actions.call_deep_research_api.run_research_api(key_trend_prompt, 4, 3)

        print(f"TASK {task_id}: ----> AFTER call_deep_research_api.run_research_api <----")

        if not report:
            error_message = "Key trends analysis failed and returned no report."
            logger.error("Key trends analysis returned no report")
            safe_callback(lambda: log_callback(task_id, error_message))
            safe_callback(lambda: update_status_callback(task_id, status="failed", data_key="error", data_value=error_message))
            return # Stop execution

        logger.info("Key trends analysis completed successfully", {
            'report_length': len(report),
            'report_preview': report[:200] + '...' if len(report) > 200 else report
        })

        # The 'report' is a string, but parse_pmf_report expects a dict.
        # We wrap it in the expected format.
        logger.debug("Parsing key trends report to JSON format")
        try:
            report_to_json = actions.markdown_to_json.parse_pmf_report({"success": True, "answer": report})
            logger.info("Key trends JSON parsing completed", {
                'parsed_keys': list(report_to_json.keys()) if report_to_json else [],
                'has_overview': bool(report_to_json.get('overview')) if report_to_json else False,
                'overview_length': len(report_to_json.get('overview', [])) if report_to_json else 0
            })
        except Exception as e:
            logger.error("Failed to parse key trends report to JSON", e, {
                'report_length': len(report) if report else 0,
                'report_preview': report[:200] + '...' if report and len(report) > 200 else report
            })
            report_to_json = {"error": "Failed to parse key trends report"}
        #Save key trends report to markdown file
        # if report:
        #     key_trends_file_path = os.path.join(task_dir, f"key_trends_report_{task_id}.md")
        #     try:
        #         with open(key_trends_file_path, "w", encoding="utf-8") as md_file:
        #             md_file.write(report)
        #         safe_callback(lambda: log_callback(task_id, f"Key trends report saved to {key_trends_file_path}"))
        #     except Exception as e:
        #         safe_callback(lambda: log_callback(task_id, f"Warning: Could not save key trends report to file: {e}"))

        safe_callback(lambda: log_callback(task_id, "Key Trends Analysis complete."))
        log_step_time("Key Trends Analysis", step_start)

        ## Generate Keywords ##
        step_start = time.time()
        logger.info("Starting keywords generation")
        safe_callback(lambda: log_callback(task_id, "Starting keywords generation..."))
        safe_callback(lambda: update_status_callback(task_id, status="generating_keywords"))

        logger.debug("Calling generate_broad_keywords function")
        query = actions.scrape_and_filter_posts.generate_broad_keywords(product_description)

        logger.info("Keywords generated successfully", {
            'keywords': query,
            'keywords_count': len(query) if query else 0
        })
        safe_callback(lambda: log_callback(task_id, f"Generated keywords: {query}"))

        ## Find subreddits based on keywords ##
        step_start = time.time()
        logger.info("Starting subreddit discovery", {'keywords': query})
        safe_callback(lambda: log_callback(task_id, "Finding subreddits..."))
        safe_callback(lambda: update_status_callback(task_id, status="finding_subreddits"))

        logger.debug("Calling search_subreddits function")
        found_subreddits = actions.scrape_and_filter_posts.search_subreddits(query)

        logger.info("Subreddits discovered", {
            'subreddits_count': len(found_subreddits),
            'subreddit_names': [sub.display_name for sub in found_subreddits] if found_subreddits else []
        })
        safe_callback(lambda: log_callback(task_id, f"Found {len(found_subreddits)} potential subreddits."))

        ## Filtering Found subreddits ##
        step_start = time.time()
        logger.info("Starting subreddit filtering", {
            'subreddits_to_filter': len(found_subreddits),
            'product_description_length': len(product_description)
        })
        safe_callback(lambda: log_callback(task_id, "Filtering subreddits..."))
        safe_callback(lambda: update_status_callback(task_id, status="filtering_subreddits"))

        logger.debug("Calling filter_subreddits_with_llm function")
        filtered = actions.scrape_and_filter_posts.filter_subreddits_with_llm(found_subreddits,
                                                                                   product_description,
                                                                                   query)

        logger.info("Subreddits filtered successfully", {
            'original_count': len(found_subreddits),
            'filtered_count': len(filtered),
            'filtered_names': [sub.display_name for sub in filtered] if filtered else []
        })
        safe_callback(lambda: log_callback(task_id, f"Filtered subreddits: {[sub.display_name for sub in filtered]}"))

        ## Scrape the subreddits ##
        step_start = time.time()
        logger.info("Starting subreddit scraping", {
            'subreddits_to_scrape': len(filtered),
            'posts_per_subreddit': 10
        })
        safe_callback(lambda: log_callback(task_id, "Starting Scraping..."))
        safe_callback(lambda: update_status_callback(task_id, status="scraping_subreddits"))

        scraped_data_list = []
        for i, sub in enumerate(filtered):
            subreddit_start = time.time()
            logger.debug(f"Scraping subreddit {i+1}/{len(filtered)}", {
                'subreddit_name': sub.display_name,
                'subreddit_id': sub.id
            })

            safe_callback(lambda i=i, sub=sub: log_callback(task_id, f"Scraping subreddit {sub.display_name} ({i+1}/{len(filtered)})..."))

            scraped_data = actions.scrape_and_filter_posts.scrape_subreddit(sub, num_posts=4)

            subreddit_duration = time.time() - subreddit_start
            logger.info(f"Subreddit scraped successfully", {
                'subreddit_name': sub.display_name,
                'posts_scraped': len(scraped_data) if scraped_data else 0,
                'duration_seconds': round(subreddit_duration, 2)
            })

            scraped_data_list.append(scraped_data)
            time.sleep(random.choice([2, 4]))  # Rate limiting

        total_posts_scraped = sum(len(data) if data else 0 for data in scraped_data_list)
        logger.info("Subreddit scraping completed", {
            'total_subreddits': len(filtered),
            'total_posts_scraped': total_posts_scraped,
            'average_posts_per_subreddit': round(total_posts_scraped / len(filtered), 1) if filtered else 0
        })
        safe_callback(lambda: log_callback(task_id, "Scraping done!"))

        ## Filter the scraped posts ##
        step_start = time.time()
        logger.info("Starting post filtering", {
            'total_posts_before_filtering': total_posts_scraped,
            'product_description_length': len(product_description)
        })
        safe_callback(lambda: update_status_callback(task_id, status="filtering_posts"))

        logger.debug("Calling filter_scraped_posts_with_llm function")
        filtered_posts = actions.scrape_and_filter_posts.filter_scraped_posts_with_llm(scraped_data=scraped_data_list,
                                                                                product_description=product_description)

        total_filtered_posts = sum(len(posts) if posts else 0 for posts in filtered_posts) if filtered_posts else 0
        logger.info("Post filtering completed", {
            'posts_before_filtering': total_posts_scraped,
            'posts_after_filtering': total_filtered_posts,
            'filtered_percentage': round((total_filtered_posts / total_posts_scraped * 100), 1) if total_posts_scraped > 0 else 0
        })
        safe_callback(lambda: log_callback(task_id, "All Irrelevant posts have been removed."))

        ## Analysis ##
        step_start = time.time()
        logger.info("Starting JTBD (Jobs to Be Done) analysis")
        safe_callback(lambda: log_callback(task_id, "🔍 Starting Prompt 1 (Jobs to Be Done)..."))
        safe_callback(lambda: update_status_callback(task_id, status="analyzing_jtbd"))

        jtbd_prompt = f"""You are a netnographic researcher studying user discussions. Here is data containing subreddit posts, comments, and scores, as well as a report. Your task is to discover the primary ‘Jobs to Be Done’ that emerge from this data.
            Here are specific trigger questions to consider:
            1. What is one thing your customer couldn't live without accomplishing? What stepping stones help your customer achieve this key job?
            2. In which different contexts do these users operate, and how do their goals or activities change with these contexts?
            3. Do they collaborate with others? Which social or interactive tasks do they need to accomplish?
            4. Which tasks or functional problems are these users trying to solve in their work or personal life?
            5. Are there potential problems they have that they might not even be aware of?
            6. Which emotional needs do they seem to be pursuing? Are there certain jobs that would give them a sense of self-satisfaction or personal identity?
            7. How do they want to be perceived by others, and how can they accomplish that image?
            8. How do they want to feel, and how can they achieve that feeling?
            9. As users interact with a product/service over its entire lifespan, do additional supporting jobs or role changes appear?
                Use these questions as a framework to:
                - Identify explicit or implicit ‘jobs’ users discuss.
                - Describe whether each job is mainly functional, social, or emotional.
                - Back up your findings with specific references or patterns in the data.
                """

        logger.debug("JTBD analysis prompt prepared", {
            'prompt_length': len(jtbd_prompt),
            'report_length': len(report),
            'filtered_posts_count': len(filtered_posts) if filtered_posts else 0
        })

        logger.debug("Calling send_report_and_filtered_posts_with_gemini for JTBD analysis")
        # MODIFIED: Pass the filtered_posts variable directly
        jtbd = actions.generate_analysis.send_report_and_filtered_posts_with_gemini(
                report_content=report,
                filtered_posts_data=filtered_posts,
                user_prompt=jtbd_prompt,
            )

        if jtbd is not None:
            logger.info("JTBD analysis completed successfully", {
                'analysis_length': len(jtbd),
                'analysis_preview': jtbd[:200] + '...' if len(jtbd) > 200 else jtbd
            })

            # Save JTBD analysis to markdown file
            # jtbd_file_path = os.path.join(task_dir, f"jtbd_analysis_{task_id}.md")
            # try:
            #     with open(jtbd_file_path, "w", encoding="utf-8") as md_file:
            #         md_file.write(jtbd)
            #     safe_callback(lambda: log_callback(task_id, f"JTBD analysis saved to {jtbd_file_path}"))
            # except Exception as e:
            #     safe_callback(lambda: log_callback(task_id, f"Warning: Could not save JTBD analysis to file: {e}"))

            safe_callback(lambda: log_callback(task_id, "JTBD Analysis complete."))
        else:
            logger.error("JTBD analysis failed - LLM returned no response")
            safe_callback(lambda: log_callback(task_id, "LLM returned no response for JTBD."))
            # Potentially raise an error or handle this case
        log_step_time("JTBD Analysis", step_start)

        step_start = time.time()
        logger.info("Starting Pains analysis")
        safe_callback(lambda: log_callback(task_id, "🔍 Starting Prompt 2 (Pains)..."))
        safe_callback(lambda: update_status_callback(task_id, status="analyzing_pains"))

        pains_prompt = """You are a netnographic researcher studying user discussions from Reddit. Here is data containing subreddit posts, comments, and scores, as well as a report. Your task is to discover the primary ‘Pains’ that emerge from this data.
            Here are specific trigger questions to consider:
            1. How do these users define ‘too costly’? Is it time, money, effort, or something else?
            2. Which frustrations, annoyances, or headaches do they mention?
            3. Which current solutions or value propositions do they find underperforming or missing features?
            4. What are the main difficulties and challenges they encounter? Are they struggling with complexity or lacking knowledge?
            5. Are they worried about negative social consequences, like a loss of face, trust, or status?
            6. Which risks do they fear, whether financial, social, or technical? What could go wrong?
            7. What’s keeping them up at night—major concerns or lingering problems?
            8. Which common mistakes or “user errors” do they run into?
            9. What barriers are preventing them from adopting a certain product or service?
            Use these questions as a framework to:
            - Identify explicit or implicit pains or frustrations.
            - Note underlying causes and potential severity of each pain.
            - Reference any direct quotes or repeated themes from the subreddit data.
            """

        logger.debug("Pains analysis prompt prepared", {
            'prompt_length': len(pains_prompt)
        })

        logger.debug("Calling send_report_and_filtered_posts_with_gemini for Pains analysis")
        # MODIFIED: Pass the filtered_posts variable directly
        pains = actions.generate_analysis.send_report_and_filtered_posts_with_gemini(
                report_content=report,
                filtered_posts_data=filtered_posts,
                user_prompt=pains_prompt,
            )

        if pains is not None:
            logger.info("Pains analysis completed successfully", {
                'analysis_length': len(pains),
                'analysis_preview': pains[:200] + '...' if len(pains) > 200 else pains
            })

            # Save Pains analysis to markdown file
            # pains_file_path = os.path.join(task_dir, f"pains_analysis_{task_id}.md")
            # try:
            #     with open(pains_file_path, "w", encoding="utf-8") as md_file:
            #         md_file.write(pains)
            #     safe_callback(lambda: log_callback(task_id, f"Pains analysis saved to {pains_file_path}"))
            # except Exception as e:
            #     safe_callback(lambda: log_callback(task_id, f"Warning: Could not save Pains analysis to file: {e}"))

            safe_callback(lambda: log_callback(task_id, "Pains Analysis complete."))
        else:
            logger.error("Pains analysis failed - LLM returned no response")
            safe_callback(lambda: log_callback(task_id, "LLM returned no response for Pains."))
            # Handle error
        log_step_time("Pains Analysis", step_start)

        step_start = time.time()
        logger.info("Starting Gains analysis")
        safe_callback(lambda: log_callback(task_id, "🔍 Starting Prompt 3 (Gains)..."))
        safe_callback(lambda: update_status_callback(task_id, status="analyzing_gains"))

        gains_prompt = """You are a netnographic researcher studying user discussions from Reddit. Below is data containing subreddit posts, comments, and scores, as well as a report. Your task is to discover the primary ‘Gains’ that emerge from this data.
            Here are specific trigger questions to consider:
            1. What savings (time, money, effort) would make users especially happy?
            2. What quality levels do they expect? What do they wish there was more or less of?
            3. Which aspects of existing solutions do they enjoy or find delightful? Are there standout features?
            4. What would make their jobs or life easier—lower learning curve, cost reduction, better support?
            5. What positive social consequences do they seek (e.g., recognition, status, influence)?
            6. Which features or improvements do they appear to want the most?
            7. What do users dream about? Are there big aspirations or “nice surprises” they mention?
            8. How do they measure success or failure? Which metrics do they care about?
            9. What would increase their likelihood of adopting a new solution? Is cost or risk reduction important?
            Use these questions as a framework to:
            - Identify explicit or implicit desires, benefits, or positive outcomes that users seek.
            - Consider how relevant each gain is to users’ real-world context.
            - Reference direct statements or recurring points from the subreddit data."""

        logger.debug("Gains analysis prompt prepared", {
            'prompt_length': len(gains_prompt)
        })

        logger.debug("Calling send_report_and_filtered_posts_with_gemini for Gains analysis")
        # MODIFIED: Pass the filtered_posts variable directly
        gains = actions.generate_analysis.send_report_and_filtered_posts_with_gemini(
                report_content=report,
                filtered_posts_data=filtered_posts,
                user_prompt=gains_prompt,
            )

        if gains is not None:
            logger.info("Gains analysis completed successfully", {
                'analysis_length': len(gains),
                'analysis_preview': gains[:200] + '...' if len(gains) > 200 else gains
            })

            # Save Gains analysis to markdown file
            # gains_file_path = os.path.join(task_dir, f"gains_analysis_{task_id}.md")
            # try:
            #     with open(gains_file_path, "w", encoding="utf-8") as md_file:
            #         md_file.write(gains)
            #     safe_callback(lambda: log_callback(task_id, f"Gains analysis saved to {gains_file_path}"))
            # except Exception as e:
            #     safe_callback(lambda: log_callback(task_id, f"Warning: Could not save Gains analysis to file: {e}"))

            safe_callback(lambda: log_callback(task_id, "Gains Analysis complete."))
        else:
            logger.error("Gains analysis failed - LLM returned no response")
            safe_callback(lambda: log_callback(task_id, "LLM returned no response for Gains."))
            # Handle error
        log_step_time("Gains Analysis", step_start)

        step_start = time.time()
        logger.info("Starting Recap analysis")
        safe_callback(lambda: log_callback(task_id, "🔍 Starting Prompt 4 (Recap)..."))
        safe_callback(lambda: update_status_callback(task_id, status="analyzing_recap"))

        recap_prompt = f"""You are a netnographic researcher. After identifying the Jobs, Pains, and Gains, please rank them as follows:
            1. List each Job from the data, giving it an Importance score from ‘insignificant’ to ‘important.
            2. List each Pain, giving it a Severity score from ‘moderate’ to ‘extreme.
            3. List each Gain, giving it a Relevance score from ‘nice to have’ to ‘essential.’
            Use the analyses you find below.
            Consider user sentiments, frequency of mentions, or any other contextual factors to justify each ranking.
            Analysis_1: {jtbd}
            Analysis_2: {pains}
            Analysis_3: {gains}
            """

        logger.debug("Recap analysis prompt prepared", {
            'prompt_length': len(recap_prompt),
            'jtbd_length': len(jtbd) if jtbd else 0,
            'pains_length': len(pains) if pains else 0,
            'gains_length': len(gains) if gains else 0
        })

        logger.debug("Calling gemini_api.generate for Recap analysis")
        recap_analysis = actions.gemini_api.generate(recap_prompt)

        if recap_analysis is not None:
            logger.info("Recap analysis completed successfully", {
                'analysis_length': len(recap_analysis),
                'analysis_preview': recap_analysis[:200] + '...' if len(recap_analysis) > 200 else recap_analysis
            })

            # Save Recap analysis to markdown file
            # recap_file_path = os.path.join(task_dir, f"recap_analysis_{task_id}.md")
            # try:
            #     with open(recap_file_path, "w", encoding="utf-8") as md_file:
            #         md_file.write(recap_analysis)
            #     safe_callback(lambda: log_callback(task_id, f"Recap analysis saved to {recap_file_path}"))
            # except Exception as e:
            #     safe_callback(lambda: log_callback(task_id, f"Warning: Could not save Recap analysis to file: {e}"))

            safe_callback(lambda: log_callback(task_id, "Recap Analysis complete."))
        else:
            logger.error("Recap analysis failed - LLM returned no response")
            safe_callback(lambda: log_callback(task_id, "LLM returned no response for Recap."))
            # Handle error
        log_step_time("Recap Analysis", step_start)

        step_start = time.time()
        logger.info("Starting Final Analysis synthesis")
        safe_callback(log_callback(task_id, "🔍 Starting Prompt 5 (Final Analysis)..."))
        safe_callback(update_status_callback(task_id, status="analyzing_final"))

        final_analysis_prompt = f"""You are a netnographic researcher. Below are four sets of analyses from the same Reddit data:
        **1. Jobs to Be Done** (Analysis 1)
        **2. Pains** (Analysis 2)
        **3. Gains** (Analysis 3)
        **4. Rankings** (Analysis 4)

        Synthesize these into one cohesive report, structured strictly in Markdown format suitable for direct rendering.

        Your report structure MUST follow these sections exactly:
        1. **Introduction**: Brief overview of the purpose of this netnographic research.
        2. **Jobs to Be Done**: Summarize the findings from Analysis 1.
        3. **Pains**: Summarize the main points from Analysis 2.
        4. **Gains**: Summarize the main points from Analysis 3.
        5. **Rankings**: Incorporate and discuss the Importance/Severity/Relevance scores from Analysis 4.
        6. **Conclusions & Recommendations**: Based on all analyses, provide final remarks or suggestions.

        Analysis_1: {jtbd}
        Analysis_2: {pains}
        Analysis_3: {gains}
        Analysis_4: {recap_analysis}

        **IMPORTANT INSTRUCTIONS:**
        - Your entire response MUST consist **only** of the raw Markdown report content itself.
        - **DO NOT** include any introductory text, preamble, explanation, or any other text before the report starts (e.g., absolutely do not start with "Okay, here is the report...").
        - **DO NOT** wrap the final report content in markdown code fences (like ``` or ```markdown). The output should be pure markdown text, not a markdown code block.
        - The response MUST start directly with the first line of the markdown report (e.g., the first character should be `#` for the main title).
        """

        logger.debug("Final analysis prompt prepared", {
            'prompt_length': len(final_analysis_prompt),
            'jtbd_length': len(jtbd) if jtbd else 0,
            'pains_length': len(pains) if pains else 0,
            'gains_length': len(gains) if gains else 0,
            'recap_length': len(recap_analysis) if recap_analysis else 0
        })

        logger.debug("Calling gemini_api.generate for Final Analysis")
        final_analysis_result = actions.gemini_api.generate(final_analysis_prompt) # Assign to variable

        # Add a check to ensure 'final_analysis_result' is not None before parsing
        if not final_analysis_result:
            error_message = "Final analysis generation failed and returned no result."
            logger.error("Final analysis generation returned no result")
            safe_callback(lambda: log_callback(task_id, error_message))
            safe_callback(lambda: update_status_callback(task_id, status="failed", data_key="error", data_value=error_message))
            return # Stop execution

        logger.info("Final analysis completed successfully", {
            'analysis_length': len(final_analysis_result),
            'analysis_preview': final_analysis_result[:200] + '...' if len(final_analysis_result) > 200 else final_analysis_result
        })

        logger.debug("Parsing final analysis to JSON format")
        try:
            final_analysis_result_json = actions.markdown_to_json.parse_final_analysis(final_analysis_result)
            logger.info("Final analysis JSON parsing completed", {
                'has_title': bool(final_analysis_result_json.get('title')) if final_analysis_result_json else False,
                'sections_count': len(final_analysis_result_json.get('sections', [])) if final_analysis_result_json else 0,
                'first_section_title': final_analysis_result_json.get('sections', [{}])[0].get('heading', 'None') if final_analysis_result_json and final_analysis_result_json.get('sections') else 'None'
            })
        except Exception as e:
            logger.error("Failed to parse final analysis to JSON", e, {
                'analysis_length': len(final_analysis_result) if final_analysis_result else 0,
                'analysis_preview': final_analysis_result[:200] + '...' if final_analysis_result and len(final_analysis_result) > 200 else final_analysis_result
            })
            final_analysis_result_json = {"error": "Failed to parse final analysis"}

        if final_analysis_result is not None:
            # Save the result to the task state
            safe_callback(lambda: update_status_callback(task_id, data_key="final_analysis", data_value=final_analysis_result))
            safe_callback(lambda: update_status_callback(task_id, status="final_analysis_ready")) # Signal Phase 3 readiness
            safe_callback(lambda: log_callback(task_id, "Final Analysis complete. Ready for Phase 3."))

            # Optional: Save to file if needed for debugging/persistence
            # with open(f"analysis_final_{task_id}.md", "w", encoding="utf-8") as md_file:
            #     md_file.write(final_analysis_result)
            # final_analysis_file_path = os.path.join(task_dir, f"analysis_final_{task_id}.md")
            # try:
            #     with open(final_analysis_file_path, "w", encoding="utf-8") as md_file:
            #         md_file.write(final_analysis_result)
            #     safe_callback(lambda: log_callback(task_id, f"Final analysis saved to {final_analysis_file_path}"))
            # except Exception as e:
            #     safe_callback(lambda: log_callback(task_id, f"Warning: Could not save final analysis to file: {e}"))

        else:
            logger.error("Final analysis failed - LLM returned no response")
            safe_callback(lambda: log_callback(task_id, "LLM returned no response for Final Analysis."))
            safe_callback(lambda: update_status_callback(task_id, status="failed", data_key="error", data_value="Final Analysis generation failed"))
            return # Stop execution if final analysis failed
        log_step_time("Final Analysis", step_start)

        step_start = time.time()
        logger.info("Starting persona generation", {'number_of_personas': 4})
        safe_callback(lambda: log_callback(task_id, "Generating personas..."))
        safe_callback(lambda: update_status_callback(task_id, status="generating_personas"))

        number = 4
        logger.debug("Calling generate_personas_json.generate_personas")
        # Assuming generate_personas_json creates 'personas.json' which we need to read
        generated_persona_data = actions.generate_personas_json.generate_personas(
            product_description, final_analysis_result, number
        )

        if not generated_persona_data:
             logger.error("Persona generation failed - returned empty list")
             safe_callback(lambda: log_callback(task_id, "Persona generation failed or returned empty list."))
             safe_callback(lambda: update_status_callback(task_id, status="failed", data_key="error", data_value="Persona generation failed"))
             return # Stop if persona generation fails

        logger.info("Persona generation completed", {
            'personas_count': len(generated_persona_data),
            'persona_names': [p.get('name', 'Unknown') for p in generated_persona_data] if generated_persona_data else []
        })
        safe_callback(lambda: log_callback(task_id, f"Generated {len(generated_persona_data)} personas structure in memory."))

        logger.debug("Calling generate_persona_prompts_and_details for detailed persona info")
        # Call the modified function to create prompts and extract card details
        detailed_persona_info = actions.create_personas.generate_persona_prompts_and_details(
            persona_data_list=generated_persona_data,
            product_description=product_description
        )

        # persona_details_file_path = os.path.join(task_dir, f"persona_details_{task_id}.json")
        # try:
        #     with open(persona_details_file_path, "w", encoding="utf-8") as json_file:
        #         json.dump(detailed_persona_info, json_file, indent=4)
        #     safe_callback(lambda: log_callback(task_id, f"Persona details saved to {persona_details_file_path}"))
        # except Exception as e:
        #     safe_callback(lambda: log_callback(task_id, f"Warning: Could not save persona details to file: {e}"))

        if not detailed_persona_info:
             logger.error("Persona prompt/details generation failed")
             safe_callback(lambda: log_callback(task_id, "Persona prompt/details generation failed."))
             safe_callback(lambda: update_status_callback(task_id, status="failed", data_key="error", data_value="Persona prompt/details generation failed"))
             return # Stop if this step fails

        logger.debug("Creating project overview prompt")
        product_overview_prompt = actions.generate_project_overview.create_overview_prompt(
            key_trends=report,
            description=product_description,
            final_analysis= final_analysis_result
        )

        logger.debug("Calling generate_project_overview.generate_project_overview")
        product_overview_json = actions.generate_project_overview.generate_project_overview(product_overview_prompt)

        logger.info("Project overview generated", {
            'overview_keys': list(product_overview_json.keys()) if product_overview_json else []
        })

        # Store the detailed info (name, prompt, card_details)
        # This structure is now richer than just names/prompts
        safe_callback(lambda: update_status_callback(task_id, data_key="persona_details", data_value=detailed_persona_info))
        safe_callback(lambda: update_status_callback(task_id, status="personas_ready")) # Signal Phase 4 readiness
        persona_names_for_log = [p.get('name', 'Unknown') for p in detailed_persona_info]
        logger.info("Personas ready for Phase 4", {
            'persona_count': len(detailed_persona_info),
            'persona_names': persona_names_for_log
        })
        safe_callback(lambda: log_callback(task_id, f"Personas ready with details: {persona_names_for_log}"))
        log_step_time("Persona Generation", step_start)

        # --- End of Background Task ---
        overall_time = time.time() - overall_start_time

        # Create timing summary
        timing_summary = []
        timing_summary.append(f"📊 **TIMING SUMMARY for Task {task_id}:**")
        timing_summary.append(f"🕐 **Total Time: {overall_time:.2f}s ({overall_time/60:.1f} minutes)**")
        timing_summary.append("")
        timing_summary.append("📋 **Step-by-step breakdown:**")

        for step, duration in step_timings.items():
            percentage = (duration / overall_time) * 100
            timing_summary.append(f"  • {step}: {duration:.2f}s ({percentage:.1f}%)")

        timing_summary_str = "\n".join(timing_summary)
        safe_callback(lambda: log_callback(task_id, timing_summary_str))
        print(f"\n{timing_summary_str}\n")

        logger.info("Analysis pipeline completed successfully", {
            'total_time_seconds': overall_time,
            'total_time_minutes': overall_time / 60,
            'step_timings': step_timings
        })

        # Save timing data to file
        timing_data = {
            "task_id": task_id,
            "total_time_seconds": overall_time,
            "total_time_minutes": overall_time / 60,
            "step_timings": step_timings,
            "timestamp": datetime.now().isoformat()
        }

        logger.info("Saving analysis results to Supabase database")
        try:
            # Prepare analysis data with both raw markdown and parsed JSON
            analysis_data = {
                "overview": product_overview_json,
                "analysis": {
                    "key_trends": {
                        "raw_markdown": report,
                        "parsed_json": report_to_json
                    },
                    "final": {
                        "raw_markdown": final_analysis_result,
                        "parsed_json": final_analysis_result_json
                    }
                },
                "status": "personas_ready",
                "locked": False
            }

            logger.info("Database update payload prepared", {
                'has_overview': product_overview_json is not None,
                'key_trends_raw_length': len(report) if report else 0,
                'key_trends_parsed_keys': list(report_to_json.keys()) if report_to_json else [],
                'final_raw_length': len(final_analysis_result) if final_analysis_result else 0,
                'final_parsed_sections': len(final_analysis_result_json.get('sections', [])) if final_analysis_result_json else 0
            })

            supabase.table("projects").update(analysis_data).eq("id", project_id).execute()

            logger.debug("Project data updated in Supabase")

           # Replace the persona insertion section in run_analysis_job with this:

            # After successfully updating the project, fetch the user's email
            logger.debug("Fetching user information for email notification")
            user_id_response = supabase.table("projects").select("user_id").eq("id", project_id).execute()
            if user_id_response.data:
                user_id = user_id_response.data[0]['user_id']
                logger.debug("Fetching user email for notification", {'user_id': user_id})
                user_email_response = supabase.table("users").select("email").eq("id", user_id).execute()
                if user_email_response.data:
                    user_email = user_email_response.data[0]['email']
                    logger.info("Sending project completion email notification", {
                        'user_email': user_email,
                        'project_name': name
                    })
                    # Send the email
                    send_project_ready_email(recipient_email=user_email, project_name=name)
                else:
                    logger.warn("Could not find user email to send notification", {'user_id': user_id})
                    safe_callback(lambda: log_callback(task_id, "Could not find user email to send notification."))
            else:
                logger.warn("Could not find user_id for the project", {'project_id': project_id})
                safe_callback(lambda: log_callback(task_id, "Could not find user_id for the project."))

            logger.info("Saving personas to Supabase database", {
                'personas_count': len(detailed_persona_info)
            })
            for i, persona in enumerate(detailed_persona_info):
                logger.debug(f"Saving persona {i+1}/{len(detailed_persona_info)}", {
                    'persona_name': persona.get("name", "Unknown")
                })
                # Access both card_details and original_data
                card_data = persona.get("card_details", {})
                prompt = persona.get("prompt", "")
                original_data = persona.get("original_data", {})

    # Extract pain points - convert string to array if needed
                pain_points_str = original_data.get("pain_points", "")
                pain_points_array = []
                if pain_points_str:
        # Split by common delimiters and clean up
                    pain_points_array = [p.strip() for p in pain_points_str.replace(';', ',').split(',') if p.strip()]

    # Extract needs/goals - convert string to array if needed
                needs_str = original_data.get("needs", "")
                goals_array = []
                if needs_str:
                    goals_array = [g.strip() for g in needs_str.replace(';', ',').split(',') if g.strip()]

    # Extract jobs_to_be_done for additional context
                jobs_str = original_data.get("jobs_to_be_done", "")
                if jobs_str and not goals_array:
                    goals_array = [jobs_str]

                supabase.table("personas").insert({
                    "project_id": project_id,
                    "name": persona.get("name", "Unknown"),
                    "role": original_data.get("job", "Not specified"),
                    "company": "Not specified",  # This field wasn't in your original schema
                    "description": original_data.get("why_important", ""),
                    "pain_points": pain_points_array,
                    "prompt": prompt,
                    "goals": goals_array,
                    "demographics": {
                        "education": original_data.get("education", "N/A"),
                        "salary_range": original_data.get("salary_range", "N/A"),
                        "hobbies": original_data.get("hobbies", "N/A"),
                        "demographics": original_data.get("demographics", "N/A"),
                        "abilities_or_passions": original_data.get("abilities_or_passions", "N/A"),
                        "population_notes": original_data.get("population_notes", "N/A"),
                        "relationship_channels": original_data.get("relationship_channels", "N/A"),
                    },
                    "ai_generated": True
                }).execute()

            logger.info("Database save completed successfully", {
                'project_updated': True,
                'personas_saved': len(detailed_persona_info)
            })
            print(f"✅ Project data and {len(detailed_persona_info)} personas saved to Supabase.")
        except Exception as e:
            error_msg = f"❌ Failed to save analysis results or personas to Supabase: {e}"
            logger.error("Failed to save to Supabase database", e, {
                'project_id': project_id,
                'personas_count': len(detailed_persona_info)
            })
            print(error_msg)
            safe_callback(lambda: log_callback(task_id, error_msg))


        # timing_file_path = os.path.join(task_dir, f"timing_report_{task_id}.json")
        # try:
        #     with open(timing_file_path, "w", encoding="utf-8") as timing_file:
        #         json.dump(timing_data, timing_file, indent=4)
        #     safe_callback(lambda: log_callback(task_id, f"⏱️ Timing report saved to {timing_file_path}"))
        # except Exception as e:
        #     safe_callback(lambda: log_callback(task_id, f"Warning: Could not save timing report: {e}"))

        # Return all the generated analysis artifacts
        return {
            "report_json": report_to_json, # JSON representation of the key trends report
            "final_analysis_json": final_analysis_result_json, # JSON representation of the final analysis),
            "persona_details": detailed_persona_info,
            "project_overview": product_overview_json
        }

    except Exception as e:
        # Enhanced error handling with detailed logging
        error_message = f"CRITICAL ERROR in run_analysis_job task {task_id}: {str(e)}\n{traceback.format_exc()}"
        logger.error("Critical error in analysis pipeline", e, {
            'task_id': task_id,
            'error_type': type(e).__name__,
            'elapsed_time_seconds': time.time() - overall_start_time
        })
        print(error_message)
        safe_callback(lambda: log_callback(task_id, f"A critical error occurred in the background task: {str(e)}"))
        safe_callback(lambda: update_status_callback(task_id, status="failed", data_key="error", data_value=error_message))

if __name__ == "__main__":
    # Example usage for testing purposes
    async def main():
        # Create async versions of the callback functions
        async def async_update_status_callback(task_id, status=None, data_key=None, data_value=None):
            print(f"Status update for {task_id}: {status}, {data_key}={data_value}")

        async def async_log_callback(task_id, message):
            print(f"Log for {task_id}: {message}")

        # Get the current event loop
        loop = asyncio.get_running_loop()

        # Run the analysis job in a thread executor since it's a synchronous function
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(
            executor,
            run_analysis_job,
            "EpiDub is an AI-powered dubbing solution designed for influencers, content creators, and wellness educators looking to expand their reach while maintaining authenticity. Unlike traditional dubbing tools that replace voices or create robotic speech, our technology enhances the creator’s original voice, preserving its natural tone and emotion across multiple languages. Users simply upload their video, and our AI analyzes speech patterns to recreate their voice authentically, ensuring a natural and engaging multilingual experience. With just a few clicks, creators can make their content accessible to global audiences without the need for re-recording or generic voiceovers. By preserving their unique voice and emotions, our AI-powered dubbing ensures a more authentic and engaging experience, strengthening audience connections.The streamlined process eliminates the need for expensive voice actors or manual adjustments, making high-quality dubbing both time- and cost-effective. Whether for YouTube, Instagram, TikTok, or wellness platforms, creators can effortlessly scale their content and expand their reach with minimal effort.",
            "timing_task",
            async_update_status_callback,
            async_log_callback,
            loop
            )
            # Save result to 'test_json' in the root directory
            root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            test_json_path = os.path.join(root_dir, "test_json")
            with open(test_json_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=4)
            print(f"Result saved to {test_json_path}")

    # Run the async main function
    asyncio.run(main())
