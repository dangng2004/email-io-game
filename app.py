"""
Email Writing Game - A Streamlit application for practicing email communication skills.

This application provides an interactive game where users write emails for specific 
scenarios and receive AI-powered feedback on their communication effectiveness.

Features:
- Multiple communication scenarios
- AI-powered email generation assistance  
- Recipient simulation and response generation
- Custom rubric generation and evaluation
- Interactive results page with detailed feedback

Dependencies:
- streamlit>=1.39.0
- openai>=1.13.0

Environment Variables:
- OPENAI_API_KEY_CLAB: Required OpenAI API key for all AI functionalities

Author: Complex Communication Research Project
"""

import streamlit as st
import openai
from datetime import datetime
from typing import Dict
import os
import glob
import re

# Game Configuration
LEVEL_TO_SCENARIO_MAPPING = {
    1: 3,  # User Level 1 maps to Backend Scenario 3
    2: 4,  # User Level 2 maps to Backend Scenario 4
    3: 2,  # User Level 3 maps to Backend Scenario 2
    # Add more levels here: 4: 1, 5: 5, etc.
}
MAX_AVAILABLE_LEVEL = max(LEVEL_TO_SCENARIO_MAPPING.keys())

# Initialize session state
if 'leaderboard' not in st.session_state:
    st.session_state.leaderboard = []
if 'current_score' not in st.session_state:
    st.session_state.current_score = None
if 'show_breakdown' not in st.session_state:
    st.session_state.show_breakdown = False
if 'evaluating' not in st.session_state:
    st.session_state.evaluating = False
if 'selected_scenario' not in st.session_state:
    st.session_state.selected_scenario = None
if 'current_page' not in st.session_state:
    st.session_state.current_page = "mode_selection"
if 'evaluation_result' not in st.session_state:
    st.session_state.evaluation_result = None
if 'recipient_reply' not in st.session_state:
    st.session_state.recipient_reply = None
if 'selected_scenario_file' not in st.session_state:
    st.session_state.selected_scenario_file = None
if 'cached_rubrics' not in st.session_state:
    st.session_state.cached_rubrics = {}
if 'app_mode' not in st.session_state:
    st.session_state.app_mode = None

class EmailGenerator:
    """
    Generates email content using OpenAI's language models.
    
    This class provides functionality to generate contextually appropriate 
    email responses based on given scenarios using GPT-4o model.
    
    Attributes:
        client (openai.OpenAI): OpenAI API client instance
        
    Methods:
        generate_email(scenario, model): Generate email content for a scenario
    """
    def __init__(self):
        # Try specific generator key first, fall back to general key
        api_key = os.getenv("OPENAI_API_KEY_CLAB")
        if not api_key:
            raise ValueError("No API key found. Set OPENAI_API_KEY_GENERATOR or OPENAI_API_KEY_CLAB environment variable.")
        self.client = openai.OpenAI(api_key=api_key)
    
    def generate_email(self, scenario: str, model: str = "gpt-4o") -> str:
        """Generate an email response for the given scenario"""
        
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are writing an email in response to the given scenario. Write only the email content, no additional commentary."},
                    {"role": "user", "content": scenario}
                ],
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
        except Exception as e:
            st.error(f"Error generating email: {str(e)}")
            return None

class EmailEvaluator:
    def __init__(self):
        # Try specific evaluator key first, fall back to general key
        api_key = os.getenv("OPENAI_API_KEY_CLAB")
        if not api_key:
            raise ValueError("No API key found. Please set the environment variable.")
        self.client = openai.OpenAI(api_key=api_key)
    
    def evaluate_email(self, scenario: str, email: str, 
                      rubric: str, recipient_reply: str, model: str = "gpt-4o") -> str:
        """Evaluate an email using the specified model, rubric, and recipient response"""
        
        # Load evaluation prompt template
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            eval_prompt_path = os.path.join(script_dir, "prompts", "evaluation", "default.txt")
            with open(eval_prompt_path, "r") as f:
                evaluation_template = f.read()
        except (FileNotFoundError, PermissionError, OSError) as e:
            # Fallback template if file not found
            evaluation_template = """
            Please evaluate the email based on the rubric provided:
            
            Scenario: {scenario}
            Rubric: {rubric}
            Email: {email}
            Response email: {response}
            
            Your evaluation:
            """
        
        # Populate the template with actual values
        evaluation_prompt = evaluation_template.format(
            scenario=scenario,
            rubric=rubric,
            email=email,
            response=recipient_reply
        )
        
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are an expert email "
                     "evaluator. Provide detailed, constructive feedback."},
                    {"role": "user", "content": evaluation_prompt}
                ],
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
        except Exception as e:
            st.error(f"Error evaluating email: {str(e)}")
            return None

class EmailRecipient:
    def __init__(self):
        # Use the same API key as other components
        api_key = os.getenv("OPENAI_API_KEY_CLAB")
        if not api_key:
            raise ValueError("No API key found. Please set the environment variable.")
        self.client = openai.OpenAI(api_key=api_key)
    
    def generate_reply(self, recipient_prompt: str, user_email: str, 
                      model: str = "gpt-4o") -> str:
        """Generate a reply email from the recipient persona"""
        
        reply_prompt = f"""
        {recipient_prompt}
        
        You just received this email:
        {user_email}
        
        Please write a reply email as this character. Write only the email content, no additional commentary.
        """
        
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are roleplaying as the specified character. Write a natural email reply that fits your persona and responds appropriately to the received email."},
                    {"role": "user", "content": reply_prompt}
                ],
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
        except Exception as e:
            st.error(f"Error generating recipient reply: {str(e)}")
            return None

class RubricGenerator:
    def __init__(self):
        # Use the same API key as other components
        api_key = os.getenv("OPENAI_API_KEY_CLAB")
        if not api_key:
            raise ValueError("No API key found. Please set the environment variable.")
        self.client = openai.OpenAI(api_key=api_key)
    
    def get_or_generate_rubric(self, scenario: str, scenario_filename: str, model: str = "gpt-4o") -> str:
        """Load existing rubric or generate and save a new one"""
        
        # First, check session state cache
        if scenario_filename in st.session_state.cached_rubrics:
            return st.session_state.cached_rubrics[scenario_filename]
        
        # Second, try to load from file (for local development)
        existing_rubric = load_rubric_from_file(scenario_filename)
        if existing_rubric:
            # Cache in session state
            st.session_state.cached_rubrics[scenario_filename] = existing_rubric
            return existing_rubric
        
        # If no existing rubric, generate a new one
        new_rubric = self.generate_rubric(scenario, model)
        if new_rubric:
            # Cache in session state
            st.session_state.cached_rubrics[scenario_filename] = new_rubric
            # Try to save to file (works in local development)
            save_rubric_to_file(scenario_filename, new_rubric)
        
        return new_rubric
    
    def generate_rubric(self, scenario: str, model: str = "gpt-4o") -> str:
        """Generate a custom rubric for evaluating emails based on the scenario"""
        
        # Load rubric generation prompt
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            rubric_prompt_path = os.path.join(script_dir, "prompts", "rubric_generation", "default.txt")
            with open(rubric_prompt_path, "r") as f:
                rubric_template = f.read()
        except (FileNotFoundError, PermissionError, OSError) as e:
            rubric_template = """I'm creating an AI-driven game where the player attempts to write emails to negotiate an outcome in a scenario. Can you look at the scenario and come up with a rubric to grade the email? The last item, on whether the email successfully achieves the goal, must always be included and worth 10 points.

Ready? Here's the scenario:

{scenario}

Rubric:"""
        
        rubric_prompt = rubric_template.format(scenario=scenario)
        
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are an expert educator creating detailed rubrics for email evaluation. Create specific, measurable criteria based on the given scenario."},
                    {"role": "user", "content": rubric_prompt}
                ],
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
        except Exception as e:
            st.error(f"Error generating rubric: {str(e)}")
            return None

def load_scenarios_from_folder(folder_path: str = "prompts/scenarios") -> Dict[str, Dict[str, str]]:
    """Load all scenario files from the specified folder"""
    scenarios = {}
    
    # Adjust path relative to current working directory
    if not os.path.isabs(folder_path):
        # Get the directory where this script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        folder_path = os.path.join(script_dir, folder_path)
    
    if os.path.exists(folder_path):
        scenario_files = glob.glob(os.path.join(folder_path, "scenario_*.txt"))
        
        for file_path in sorted(scenario_files):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    
                # Extract scenario number from filename
                filename = os.path.basename(file_path)
                scenario_num = filename.replace('scenario_', '').replace('.txt', '')
                
                # Create display name
                display_name = f"Scenario {scenario_num}"
                
                # Try to extract a summary from the first line or paragraph
                first_line = content.split('\n')[0][:100]
                if len(first_line) == 100:
                    first_line += "..."
                
                display_name += f" - {first_line}"
                
                scenarios[display_name] = {
                    'content': content,
                    'filename': filename
                }
                
            except Exception as e:
                st.error(f"Error loading scenario from {file_path}: {str(e)}")
    
    return scenarios

def load_recipient_prompt(scenario_filename: str) -> str:
    """Load recipient prompt for a given scenario filename"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    recipient_path = os.path.join(script_dir, "prompts", "recipients", scenario_filename)
    
    if os.path.exists(recipient_path):
        try:
            with open(recipient_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception as e:
            st.error(f"Error loading recipient prompt: {str(e)}")
            return ""
    else:
        return f"You are the recipient of an email. Please respond naturally and appropriately to the email you receive."

def load_rubric_from_file(scenario_filename: str) -> str:
    """Load rubric from rubrics folder for a given scenario filename"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    rubric_path = os.path.join(script_dir, "rubrics", scenario_filename)
    
    if os.path.exists(rubric_path):
        try:
            with open(rubric_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception as e:
            st.error(f"Error loading rubric: {str(e)}")
            return None
    else:
        return None

def save_rubric_to_file(scenario_filename: str, rubric: str) -> bool:
    """Save generated rubric to rubrics folder"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    rubrics_dir = os.path.join(script_dir, "rubrics")
    
    # Create rubrics directory if it doesn't exist
    if not os.path.exists(rubrics_dir):
        try:
            os.makedirs(rubrics_dir)
        except Exception as e:
            st.error(f"Error creating rubrics directory: {str(e)}")
            return False
    
    rubric_path = os.path.join(rubrics_dir, scenario_filename)
    
    try:
        with open(rubric_path, 'w', encoding='utf-8') as f:
            f.write(rubric)
        return True
    except Exception as e:
        st.error(f"Error saving rubric: {str(e)}")
        return False

def extract_goal_achievement_score(evaluation_text: str) -> bool:
    """
    Extract the goal achievement from the evaluation text and determine if user succeeded.
    
    The final rubric item uses a Yes/No format:
    "The email successfully negotiates the goal: Yes" or "No"
    
    Args:
        evaluation_text: The AI evaluation text containing Yes/No assessment
        
    Returns:
        bool: True if "Yes", False if "No" or cannot be parsed
    """
    import re
    
    # Look for the goal achievement pattern: "goal: Yes" or "goal: No"
    # Case-insensitive search for various phrasings
    goal_patterns = [
        r'(?:email\s+)?successfully\s+negotiates?\s+(?:the\s+)?goal\s*[:]\s*(yes|no)',
        r'(?:achieve|negotiat).*?goal\s*[:]\s*(yes|no)',
        r'goal\s+(?:achievement|success)\s*[:]\s*(yes|no)',
        r'goal\s*[:]\s*(yes|no)',
    ]
    
    # Search through the evaluation text
    evaluation_lower = evaluation_text.lower()
    
    for pattern in goal_patterns:
        match = re.search(pattern, evaluation_lower)
        if match:
            result = match.group(1).strip()
            return result == "yes"
    
    # If we can't find the goal achievement assessment, be conservative and return False
    return False

def show_mode_selection_page():
    """Show the mode selection page"""
    st.markdown("""
    <style>
    .mode-header {
        text-align: center;
        padding: 2rem 0;
    }
    .mode-card {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 2rem;
        margin: 1rem 0;
        border-left: 5px solid #007bff;
        height: 200px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .user-card {
        border-left-color: #28a745 !important;
    }
    .dev-card {
        border-left-color: #ffc107 !important;
    }
    </style>
    
    <div class="mode-header">
    
    # 📧 Email.io: Can You Write Better Emails than AI? 
    </div>
    """, unsafe_allow_html=True)
    
    # Create two columns for the mode selection
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        <div class="mode-card user-card">
        <h3>👤 User Mode</h3>
        <p>Play as a user.</p>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("🚀 Play Now", type="primary", use_container_width=True):
            st.session_state.app_mode = "user"
            st.session_state.current_page = "game"
            st.rerun()
    
    with col2:
        st.markdown("""
        <div class="mode-card dev-card">
        <h3>🛠️ Developer Mode</h3>
        <p>If you want to customize the scenario and prompts to models.</p>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("⚙️ Run As Developer", type="secondary", use_container_width=True):
            st.session_state.app_mode = "developer"
            st.session_state.current_page = "game"
            st.rerun()
    
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #6c757d;">
    <small>
    💡 <strong>Tip:</strong> You can switch modes anytime by refreshing the page.
    </small>
    </div>
    """, unsafe_allow_html=True)

def show_game_page():
    """Show the main game interface"""
    
    # Add mode indicator and back button
    mode_col, back_col = st.columns([4, 1])
    with mode_col:
        mode_display = "👤 User Mode" if st.session_state.app_mode == "user" else "🛠️ Developer Mode"
        st.markdown(f"**Current Mode:** {mode_display}")
    with back_col:
        if st.button("↩️ Change Mode", help="Go back to mode selection"):
            st.session_state.current_page = "mode_selection"
            st.session_state.app_mode = None
            st.rerun()
    
    st.markdown("""
    <style>
    .compact-header h2 {
        margin-top: 0rem !important;
        margin-bottom: 0.5rem !important;
        padding-top: 0rem !important;
    }
    </style>
    <div class="compact-header">
    
    ## 📧 Email.io: Can You Write Better Emails than AI?
    
    </div>
    """, unsafe_allow_html=True)
    st.markdown("**Write emails for various scenarios and AI-generated responses!**")
    
    # Load available scenarios
    available_scenarios = load_scenarios_from_folder()
    
    # Check API key availability
    try:
        api_keys_available = bool(os.getenv("OPENAI_API_KEY_CLAB"))
    except Exception as e:
        api_keys_available = False
    
    # Render UI based on mode
    if st.session_state.app_mode == "developer":
        show_developer_interface(available_scenarios, api_keys_available)
    else:  # user mode
        show_user_interface_with_history(available_scenarios, api_keys_available)

def show_user_interface_with_history(available_scenarios, api_keys_available):
    """Show the user interface with history-based navigation"""
    # Set default model for user version (no sidebar configuration)
    model = "gpt-4o"
    
    # Initialize current level if not set (user-facing levels start from 1)
    if 'current_level' not in st.session_state:
        st.session_state.current_level = 1  # Start with user level 1
    
    # Initialize level completion tracking
    if 'completed_levels' not in st.session_state:
        st.session_state.completed_levels = set()  # Track which levels are completed
    
    # Initialize email storage by level
    if 'level_emails' not in st.session_state:
        st.session_state.level_emails = {}  # Store emails for each level
    
    # Initialize page history system
    if 'page_history' not in st.session_state:
        st.session_state.page_history = [{"type": "scenario", "level": 1}]  # Start with scenario 1
    if 'current_history_index' not in st.session_state:
        st.session_state.current_history_index = 0
    if 'level_evaluations' not in st.session_state:
        st.session_state.level_evaluations = {}  # Store evaluation results by level
    
    # Use the global level mapping
    level_to_scenario_mapping = LEVEL_TO_SCENARIO_MAPPING
    max_level = MAX_AVAILABLE_LEVEL
    
    # Determine current page from history
    current_page = st.session_state.page_history[st.session_state.current_history_index]
    current_level_from_history = current_page["level"]
    
    # Navigation header with history controls
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        # Back button (browser-like)
        can_go_back = st.session_state.current_history_index > 0
        if st.button("← Back", disabled=not can_go_back, help="Go back in history"):
            st.session_state.current_history_index -= 1
            st.rerun()
    
    with col2:
        # Current page indicator
        page_type = current_page["type"]
        page_title = f"Level {current_level_from_history} - {'Scenario' if page_type == 'scenario' else 'Results'}"
        st.markdown(f"**🎮 {page_title}**")
    
    with col3:
        # Forward button (browser-like)
        can_go_forward = st.session_state.current_history_index < len(st.session_state.page_history) - 1
        if st.button("Forward →", disabled=not can_go_forward, help="Go forward in history"):
            st.session_state.current_history_index += 1
            st.rerun()
    
    # Level progression info
    st.info("🎯 **Level Progression**: Navigate through your completed levels using Back/Forward buttons!")
    
    # Show overall progress
    completed_count = len(st.session_state.completed_levels)
    progress_percentage = (completed_count / max_level) * 100
    st.progress(progress_percentage / 100)
    st.caption(f"Progress: {completed_count}/{max_level} levels completed ({progress_percentage:.0f}%)")
    
    # Show different content based on current page type
    if current_page["type"] == "scenario":
        show_scenario_page(current_level_from_history, available_scenarios, level_to_scenario_mapping, api_keys_available, model)
    else:  # evaluation page
        show_evaluation_page_from_history(current_level_from_history)

def show_scenario_page(level, available_scenarios, level_to_scenario_mapping, api_keys_available, model):
    """Show the scenario page for a specific level"""
    
    # Get backend scenario ID from user level
    backend_scenario_id = level_to_scenario_mapping.get(level, 3)  # Default to scenario 3
    
    # Get scenario data based on backend scenario ID
    scenario_data = None
    scenario_content = ""
    
    if available_scenarios:
        # Look for the backend scenario ID
        target_scenario = f"scenario_{backend_scenario_id}"
        for scenario_name, scenario_info in available_scenarios.items():
            if target_scenario in scenario_info['filename'].lower() or str(backend_scenario_id) in scenario_name:
                scenario_data = scenario_info
                scenario_content = scenario_info['content']
                st.session_state.selected_scenario = scenario_content
                st.session_state.selected_scenario_file = scenario_info['filename']
                break
        
        if not scenario_data:
            st.warning(f"Level {level} scenario not found. Using default scenario.")
            scenario_content = """You are coordinating a weekend trip to a national park with 5 friends. You need to organize transportation, accommodation, and activities. Some friends prefer camping while others want a hotel. The trip is in 3 weeks and you need everyone to confirm their participation and preferences by Friday."""
    else:
        # Fallback to default scenario if no scenarios found
        scenario_content = """You are coordinating a weekend trip to a national park with 5 friends. You need to organize transportation, accommodation, and activities. Some friends prefer camping while others want a hotel. The trip is in 3 weeks and you need everyone to confirm their participation and preferences by Friday."""
        st.warning("No scenarios found in manual folder. Using default scenario.")
    
    # Scenario section
    st.subheader("📋 Scenario")
    
    # Display scenario content with proper line breaks
    # Convert line breaks to HTML breaks for proper display
    formatted_content = scenario_content.replace('\n', '<br>')
    st.markdown(
        f"""
        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; border-left: 4px solid #007bff;">
        {formatted_content}
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Set scenario for processing
    scenario = scenario_content
    
    # Email input section
    st.subheader("✍️ Your Email")
    
    # Pre-populate email if returning to a completed level
    initial_email_value = ""
    if level in st.session_state.level_emails:
        initial_email_value = st.session_state.level_emails[level]
    
    # Email text area - uses key to maintain state automatically
    email_content = st.text_area(
        "Write your email here",
        value=initial_email_value,
        height=400,
        max_chars=3000,  # Prevent excessively long emails
        placeholder="Type your email response to the scenario above...",
        help="Write the best email you can for the given scenario",
        key=f"email_input_level_{level}"  # Unique key per level
    )

    # Submit button
    st.markdown("---")
    if st.button(
        "📝 Send",
        type="primary",
        disabled=not api_keys_available or not email_content.strip(),
        help="Submit your email for AI evaluation"
    ):
        if not email_content.strip():
            st.error("Please write an email before submitting!")
        elif not api_keys_available:
            st.error("API keys not available")
        else:
            # Process email evaluation and update history
            process_email_evaluation_with_history(scenario, email_content, model, level)

def show_evaluation_page_from_history(level):
    """Show the stored evaluation results for a specific level"""
    
    if level in st.session_state.level_evaluations:
        result = st.session_state.level_evaluations[level]
        
        # Show the scenario
        st.subheader("📋 Scenario")
        st.text_area("", value=result["scenario"], height=200, disabled=True)
        
        # Show the email
        st.subheader("✍️ Your Email")
        st.text_area("", value=result["email"], height=300, disabled=True)
        
        # Show the recipient reply
        if "recipient_reply" in result:
            st.subheader("📨 Recipient's Reply")
            st.markdown(result["recipient_reply"])
        
        # Show goal achievement status
        if "goal_achieved" in result:
            if result["goal_achieved"]:
                st.success("🎉 **Success!** You persuaded the recipient and completed this level!")
            else:
                st.error("❌ **Goal Not Achieved** - You can try this level again to improve your result.")
        
        # Show the generated rubric (collapsible)
        if "rubric" in result:
            with st.expander("📏 Evaluation Rubric", expanded=False):
                st.markdown(result["rubric"])
        
        # Show the evaluation with improved formatting (collapsible)
        with st.expander("🤖 AI Evaluation", expanded=True):
            st.markdown("""
            <style>
            .quote-box {
                background-color: #fff3cd;
                border: 1px solid #ffeaa7;
                border-radius: 5px;
                padding: 12px;
                margin: 4px 0 24px 0;
                font-style: italic;
                white-space: pre-line;
            }
            .evaluation-content {
                font-size: 0.9rem !important;
                line-height: 1.5 !important;
            }
            .evaluation-content p {
                font-size: 0.9rem !important;
                line-height: 1.5 !important;
                margin-bottom: 1rem !important;
            }
            .evaluation-content ul {
                list-style: none !important;
                padding-left: 0 !important;
            }
            .evaluation-content li {
                margin-bottom: 1rem !important;
                font-size: 0.9rem !important;
            }
            .evaluation-item {
                margin-bottom: 4px;
            }
            .evaluation-item:first-child {
                margin-top: 0;
            }
            </style>
            """, unsafe_allow_html=True)
            
            # Process evaluation to add yellow boxes for quotes/rationales  
            evaluation_text = result["evaluation"]
            
            # Remove bullet points first
            processed_evaluation = re.sub(r'^\s*[-•*]\s*', '', evaluation_text, flags=re.MULTILINE)
            
            # Process evaluation to add yellow boxes for quotes and rationales
            def process_quotes_and_rationales(text):
                lines = text.split('\n')
                # Remove empty lines
                lines = [line for line in lines if line.strip()]
                processed_lines = []

                i = 0
                while i < len(lines):
                    line = lines[i].strip() 

                    if line.startswith('Quote:') or line.startswith('Rationale:'):
                        # Check if there's a next line and if it's a Rationale
                        if i + 1 < len(lines):
                            next_line = lines[i + 1].strip()
                            if next_line.startswith('Rationale:'):
                                line = f'{line}\n\n{next_line.strip()}'
                                i += 1  # Skip the next line since we've processed it
                        
                        processed_lines.append(f'<div class="quote-box">{line.strip()}</div>')
                    elif line:  # Only add non-empty lines
                        processed_lines.append(f'<div class="evaluation-item">{line}</div>')
                    
                    i += 1  # Move to next line
                
                return '\n'.join(processed_lines)
            
            processed_evaluation = process_quotes_and_rationales(processed_evaluation)
            
            st.markdown(f'<div class="evaluation-content">{processed_evaluation}</div>', unsafe_allow_html=True)
        
        # Show additional navigation options
        st.markdown("---")
        
        # Show "Continue to Next Level" button if this was successful and there are more levels
        if result.get("goal_achieved") and level < MAX_AVAILABLE_LEVEL:
            next_level = level + 1
            if st.button(f"Continue to Level {next_level} →", type="primary"):
                # Add next level to history if not already there
                next_page = {"type": "scenario", "level": next_level}
                if next_page not in st.session_state.page_history:
                    st.session_state.page_history.append(next_page)
                # Navigate to next level
                st.session_state.current_history_index = len(st.session_state.page_history) - 1
                st.rerun()
        
        # Show "Try Again" button if this was unsuccessful
        elif not result.get("goal_achieved"):
            if st.button(f"Try Level {level} Again →", type="primary"):
                # Navigate back to the scenario page for this level
                scenario_page = {"type": "scenario", "level": level}
                # Find the scenario page in history or add it
                try:
                    scenario_index = st.session_state.page_history.index(scenario_page)
                    st.session_state.current_history_index = scenario_index
                except ValueError:
                    # Add scenario page to history if not found
                    st.session_state.page_history.append(scenario_page)
                    st.session_state.current_history_index = len(st.session_state.page_history) - 1
                st.rerun()
    else:
        st.error(f"No evaluation results found for Level {level}")

def process_email_evaluation_with_history(scenario, email_content, model, level):
    """Process email evaluation and update history navigation"""
    # Show loading screen with multiple steps
    progress_text = st.empty()
    progress_bar = st.progress(0)
    
    try:
        # Store the email for this level
        if 'level_emails' not in st.session_state:
            st.session_state.level_emails = {}
        st.session_state.level_emails[level] = email_content
        
        # Step 1: Load or generate rubric
        progress_text.text("🔄 Loading evaluation rubric...")
        progress_bar.progress(0.25)
        
        rubric_generator = RubricGenerator()
        scenario_filename = st.session_state.get("selected_scenario_file", "")
        
        if scenario_filename:
            rubric = rubric_generator.get_or_generate_rubric(scenario, scenario_filename, model)
        else:
            # Fallback to direct generation if no filename available
            rubric = rubric_generator.generate_rubric(scenario, model)
        
        if not rubric:
            st.error("Failed to generate rubric")
            return
        
        # Step 2: Generate recipient reply
        progress_text.text("📨 Awaiting response from recipient...")
        progress_bar.progress(0.5)
        
        # Load default recipient prompt based on selected scenario
        if st.session_state.get("selected_scenario_file"):
            default_recipient_prompt = load_recipient_prompt(st.session_state.selected_scenario_file)
        else:
            default_recipient_prompt = "You are the recipient of an email. Please respond naturally and appropriately to the email you receive."
        
        recipient = EmailRecipient()
        recipient_reply = recipient.generate_reply(
            default_recipient_prompt, email_content, model
        )
        
        if not recipient_reply:
            st.error("Failed to generate recipient reply")
            return
        
        # Step 3: Evaluate the email using the generated rubric
        progress_text.text("📊 Evaluating your email...")
        progress_bar.progress(0.75)
        
        evaluator = EmailEvaluator()
        evaluation_result = evaluator.evaluate_email(
            scenario, email_content, rubric, recipient_reply, model
        )
        
        if not evaluation_result:
            st.error("Failed to evaluate email")
            return
        
        # Step 4: Complete
        progress_text.text("✅ Evaluation complete!")
        progress_bar.progress(1.0)
        
        # Check if user successfully achieved the goal
        goal_success = extract_goal_achievement_score(evaluation_result)
        
        # Store evaluation results for this level
        evaluation_data = {
            "scenario": scenario,
            "email": email_content,
            "rubric": rubric,
            "recipient_reply": recipient_reply,
            "evaluation": evaluation_result,
            "goal_achieved": goal_success,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        if 'level_evaluations' not in st.session_state:
            st.session_state.level_evaluations = {}
        st.session_state.level_evaluations[level] = evaluation_data
        
        # Update completion status
        if 'completed_levels' not in st.session_state:
            st.session_state.completed_levels = set()
            
        if goal_success:
            st.session_state.completed_levels.add(level)
        
        # HISTORY MANAGEMENT: Truncate history when retrying a level
        # Find the current scenario page index in history
        current_scenario_page = {"type": "scenario", "level": level}
        current_scenario_index = None
        
        for i, page in enumerate(st.session_state.page_history):
            if page["type"] == "scenario" and page["level"] == level:
                current_scenario_index = i
                break
        
        if current_scenario_index is not None:
            # Truncate history to include only up to the current scenario page
            # This erases all future history when retrying a level
            st.session_state.page_history = st.session_state.page_history[:current_scenario_index + 1]
        
        # Add evaluation page to history (right after the scenario)
        evaluation_page = {"type": "evaluation", "level": level}
        st.session_state.page_history.append(evaluation_page)
        st.session_state.current_history_index = len(st.session_state.page_history) - 1
        
        # If successful and there are more levels, prepare next level scenario in history
        if goal_success and level < MAX_AVAILABLE_LEVEL:
            next_level = level + 1
            next_scenario_page = {"type": "scenario", "level": next_level}
            st.session_state.page_history.append(next_scenario_page)
        
        st.rerun()
        
    except Exception as e:
        st.error(f"Error during processing: {str(e)}")

def show_user_interface(available_scenarios, api_keys_available):
    """Show the simplified user interface"""
    # Set default model for user version (no sidebar configuration)
    model = "gpt-4o"
    
    # Initialize current level if not set (user-facing levels start from 1)
    if 'current_level' not in st.session_state:
        st.session_state.current_level = 1  # Start with user level 1
    
    # Initialize level completion tracking
    if 'completed_levels' not in st.session_state:
        st.session_state.completed_levels = set()  # Track which levels are completed
    
    # Initialize email storage by level
    if 'level_emails' not in st.session_state:
        st.session_state.level_emails = {}  # Store emails for each level
    
    # Initialize page history system
    if 'page_history' not in st.session_state:
        st.session_state.page_history = [{"type": "scenario", "level": 1}]  # Start with scenario 1
    if 'current_history_index' not in st.session_state:
        st.session_state.current_history_index = 0
    if 'level_evaluations' not in st.session_state:
        st.session_state.level_evaluations = {}  # Store evaluation results by level
    
    # Use the global level mapping
    level_to_scenario_mapping = LEVEL_TO_SCENARIO_MAPPING
    max_level = MAX_AVAILABLE_LEVEL
    
    # Determine current page from history
    current_page = st.session_state.page_history[st.session_state.current_history_index]
    current_level_from_history = current_page["level"]
    
    # Navigation header with history controls
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        # Back button (browser-like)
        can_go_back = st.session_state.current_history_index > 0
        if st.button("← Back", disabled=not can_go_back, help="Go back in history"):
            st.session_state.current_history_index -= 1
            st.rerun()
    
    with col2:
        # Current page indicator
        page_type = current_page["type"]
        page_title = f"Level {current_level_from_history} - {'Scenario' if page_type == 'scenario' else 'Results'}"
        st.markdown(f"**🎮 {page_title}**")
    
    with col3:
        # Forward button (browser-like)
        can_go_forward = st.session_state.current_history_index < len(st.session_state.page_history) - 1
        if st.button("Forward →", disabled=not can_go_forward, help="Go forward in history"):
            st.session_state.current_history_index += 1
            st.rerun()
    
    # Level progression info
    st.info("🎯 **Level Progression**: Navigate through your completed levels using Back/Forward buttons!")
    
    # Show overall progress
    completed_count = len(st.session_state.completed_levels)
    progress_percentage = (completed_count / max_level) * 100
    st.progress(progress_percentage / 100)
    st.caption(f"Progress: {completed_count}/{max_level} levels completed ({progress_percentage:.0f}%)")
    
    # Scenario section
    st.subheader("📋 Scenario")
    
    # Get backend scenario ID from user level
    backend_scenario_id = level_to_scenario_mapping.get(st.session_state.current_level, 3)  # Default to scenario 3
    
    # Get scenario data based on backend scenario ID
    scenario_data = None
    scenario_content = ""
    
    if available_scenarios:
        # Look for the backend scenario ID
        target_scenario = f"scenario_{backend_scenario_id}"
        for scenario_name, scenario_info in available_scenarios.items():
            if target_scenario in scenario_info['filename'].lower() or str(backend_scenario_id) in scenario_name:
                scenario_data = scenario_info
                scenario_content = scenario_info['content']
                st.session_state.selected_scenario = scenario_content
                st.session_state.selected_scenario_file = scenario_info['filename']
                break
        
        if not scenario_data:
            st.warning(f"Level {st.session_state.current_level} scenario not found. Using default scenario.")
            scenario_content = """You are coordinating a weekend trip to a national park with 5 friends. You need to organize transportation, accommodation, and activities. Some friends prefer camping while others want a hotel. The trip is in 3 weeks and you need everyone to confirm their participation and preferences by Friday."""
    else:
        # Fallback to default scenario if no scenarios found
        scenario_content = """You are coordinating a weekend trip to a national park with 5 friends. You need to organize transportation, accommodation, and activities. Some friends prefer camping while others want a hotel. The trip is in 3 weeks and you need everyone to confirm their participation and preferences by Friday."""
        st.warning("No scenarios found in manual folder. Using default scenario.")
    
    # Display scenario content with proper line breaks
    # Convert line breaks to HTML breaks for proper display
    formatted_content = scenario_content.replace('\n', '<br>')
    st.markdown(
        f"""
        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; border-left: 4px solid #007bff;">
        {formatted_content}
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Set scenario for processing
    scenario = scenario_content
    
    # Email input section (no AI generation in user mode)
    st.subheader("✍️ Your Email")
    
    # Pre-populate email if returning to a completed level
    initial_email_value = ""
    if st.session_state.current_level in st.session_state.level_emails:
        initial_email_value = st.session_state.level_emails[st.session_state.current_level]
    
    # Email text area - uses key to maintain state automatically
    email_content = st.text_area(
        "Write your email here",
        value=initial_email_value,
        height=400,
        max_chars=3000,  # Prevent excessively long emails
        placeholder="Type your email response to the scenario above...",
        help="Write the best email you can for the given scenario",
        key=f"email_input_level_{st.session_state.current_level}"  # Unique key per level
    )

    # Submit button for user mode
    st.markdown("---")
    if st.button(
        "📝 Send",
        type="primary",
        disabled=not api_keys_available or not email_content.strip(),
        help="Submit your email for AI evaluation"
    ):
        if not email_content.strip():
            st.error("Please write an email before submitting!")
        elif not api_keys_available:
            st.error("API keys not available")
        else:
            # Process email evaluation using default settings for user mode
            process_email_evaluation_user_mode(scenario, email_content, model)

def show_developer_interface(available_scenarios, api_keys_available):
    """Show the full developer interface with all controls"""
    # Sidebar for configuration
    with st.sidebar:
        st.subheader("Configuration")
        
        # API Key status
        if api_keys_available:
            st.success("✅ API keys loaded from environment")
        else:
            st.error("❌ Missing API keys")
            st.info("Set OPENAI_API_KEY_CLAB environment variable")
        
        # Model selection
        model = st.selectbox(
            "Evaluator Model",
            ["gpt-4o"],
            help="Select the model to evaluate emails"
        )
        
        st.markdown("---")
        st.markdown("**Scenarios**")
        if available_scenarios:
            st.success(f"Loaded {len(available_scenarios)} scenario(s)")
        else:
            st.warning("No scenarios found in manual folder")
    
    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Scenario section
        st.subheader("📋 Scenario")
        
        # Scenario selection dropdown
        if available_scenarios:
            scenario_options = ["Select a scenario..."] + list(available_scenarios.keys())
            selected_scenario_name = st.selectbox(
                "Choose a scenario",
                scenario_options,
                index=0,
                help="Select from available scenarios in the manual folder"
            )
            
            if selected_scenario_name != "Select a scenario...":
                scenario_data = available_scenarios[selected_scenario_name]
                scenario_content = scenario_data['content']
                st.session_state.selected_scenario = scenario_content
                st.session_state.selected_scenario_file = scenario_data['filename']
            else:
                scenario_content = st.session_state.selected_scenario or ""
        else:
            # Fallback to default scenario if no scenarios found
            scenario_content = """You are coordinating a weekend trip to a national park with 5 friends. You need to organize transportation, accommodation, and activities. Some friends prefer camping while others want a hotel. The trip is in 3 weeks and you need everyone to confirm their participation and preferences by Friday."""
            st.warning("No scenarios found in manual folder. Using default scenario.")
        
        scenario = st.text_area(
            "Current Scenario",
            value=scenario_content,
            height=350,
            max_chars=5000,  # Prevent excessively long scenarios
            help="The scenario for which participants will write emails"
        )
        
        # Email input section
        col_email_header, col_ai_button = st.columns([3, 1])
        with col_email_header:
            st.subheader("✍️ Your Email")
        with col_ai_button:
            if st.button("🤖 Generate email with AI", help="Generate an email using AI for the current scenario"):
                if api_keys_available and scenario.strip():
                    with st.spinner("🤖 AI is writing an email..."):
                        try:
                            generator = EmailGenerator()
                            generated_email = generator.generate_email(scenario, model)
                            if generated_email:
                                # Set the generated email directly in the widget state
                                st.session_state["email_input"] = generated_email
                                st.success("✅ Email generated!")
                                st.rerun()
                            else:
                                st.error("Failed to generate email")
                        except Exception as e:
                            st.error(f"Error initializing generator: {str(e)}")
                elif not api_keys_available:
                    st.error("API keys not available")
                else:
                    st.error("Please select a scenario first")
        
        # Email text area - uses key to maintain state automatically
        email_content = st.text_area(
            "Write your email here",
            height=400,
            max_chars=3000,  # Prevent excessively long emails
            placeholder="Type your email response to the scenario above, or use the AI generation button...",
            help="Write the best email you can for the given scenario, or generate one with AI",
            key="email_input"
        )
    
    with col2:
        # Developer mode section
        st.subheader("🛠️ Developer Mode")
        
        # Recipient persona section (collapsible)
        with st.expander("📨 Recipient Persona", expanded=False):
            st.markdown("*Define who will reply to the user's email*")
            
            # Load recipient prompt based on selected scenario
            if st.session_state.selected_scenario_file:
                default_recipient_prompt = load_recipient_prompt(st.session_state.selected_scenario_file)
            else:
                default_recipient_prompt = "You are the recipient of an email. Please respond naturally and appropriately to the email you receive."
            
            recipient_prompt = st.text_area(
                "Recipient Persona Instructions",
                value=default_recipient_prompt,
                height=300,
                help="Instructions for the AI to roleplay as the email recipient",
                key="recipient_prompt"
            )
        
        # Evaluator prompt section (collapsible)
        with st.expander("📝 Grading Instructions", expanded=False):
            st.markdown("*Tell the AI evaluator how to assess the email*")
            
            try:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                eval_prompt_path = os.path.join(script_dir, "prompts", "evaluation", "default.txt")
                with open(eval_prompt_path, "r") as f:
                    default_prompt = f.read()
            except (FileNotFoundError, PermissionError, OSError) as e:
                default_prompt = """Given the following scenario, how would you evaluate the email? Please come up with some criteria and then evaluate the email based on those criteria. Give a numerical scale for each criterion and tally up a total score for the email."""
            
            evaluator_prompt = st.text_area(
                "Grading Instructions",
                value=default_prompt,
                height=300,
                help="Instructions for the AI evaluator on how to assess emails",
                key="evaluator_prompt"
            )
    
    # Submit button for developer mode
    st.markdown("---")
    if st.button(
        "📝 Send",
        type="primary",
        disabled=not api_keys_available or not email_content.strip(),
        help="Submit your email for AI evaluation"
    ):
        if not email_content.strip():
            st.error("Please write an email before submitting!")
        elif not api_keys_available:
            st.error("API keys not available")
        else:
            # Process email evaluation using custom settings from developer mode
            process_email_evaluation_developer_mode(scenario, email_content, model)

def process_email_evaluation_user_mode(scenario, email_content, model):
    """Process email evaluation using default settings for user mode"""
    # Show loading screen with multiple steps
    progress_text = st.empty()
    progress_bar = st.progress(0)
    
    try:
        # Step 1: Load or generate rubric
        progress_text.text("🔄 Loading evaluation rubric...")
        progress_bar.progress(0.25)
        
        rubric_generator = RubricGenerator()
        scenario_filename = st.session_state.get("selected_scenario_file", "")
        
        if scenario_filename:
            rubric = rubric_generator.get_or_generate_rubric(scenario, scenario_filename, model)
        else:
            # Fallback to direct generation if no filename available
            rubric = rubric_generator.generate_rubric(scenario, model)
        
        if not rubric:
            st.error("Failed to generate rubric")
            return
        
        # Step 2: Generate recipient reply (using default recipient prompt for user version)
        progress_text.text("📨 Awaiting response from recipient...")
        progress_bar.progress(0.5)
        
        # Load default recipient prompt based on selected scenario
        if st.session_state.get("selected_scenario_file"):
            default_recipient_prompt = load_recipient_prompt(st.session_state.selected_scenario_file)
        else:
            default_recipient_prompt = "You are the recipient of an email. Please respond naturally and appropriately to the email you receive."
        
        recipient = EmailRecipient()
        recipient_reply = recipient.generate_reply(
            default_recipient_prompt, email_content, model
        )
        
        if not recipient_reply:
            st.error("Failed to generate recipient reply")
            return
        
        # Step 3: Evaluate the email using the generated rubric (using default evaluator prompt)
        progress_text.text("📊 Evaluating your email...")
        progress_bar.progress(0.75)
        
        evaluator = EmailEvaluator()
        evaluation_result = evaluator.evaluate_email(
            scenario, email_content, rubric, recipient_reply, model
        )
        
        if not evaluation_result:
            st.error("Failed to evaluate email")
            return
        
        # Step 4: Complete
        progress_text.text("✅ Evaluation complete!")
        progress_bar.progress(1.0)
        
        # Store all data for results page
        st.session_state.evaluation_result = {
            "scenario": scenario,
            "email": email_content,
            "rubric": rubric,
            "recipient_reply": recipient_reply,
            "evaluation": evaluation_result,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Store the email for this level
        if 'current_level' in st.session_state:
            if 'level_emails' not in st.session_state:
                st.session_state.level_emails = {}
            st.session_state.level_emails[st.session_state.current_level] = email_content
        
        # Check if user successfully achieved the goal before marking level complete
        goal_success = extract_goal_achievement_score(evaluation_result)
        
        # Handle level progression based on success (only for user mode)
        if 'current_level' in st.session_state:
            if 'completed_levels' not in st.session_state:
                st.session_state.completed_levels = set()
                
            if goal_success:
                # Mark current level as completed
                st.session_state.completed_levels.add(st.session_state.current_level)
                
                # Store the level they just completed for navigation
                st.session_state.evaluation_result["completed_level"] = st.session_state.current_level
                
                # Auto-advance to next level if available
                if st.session_state.current_level < MAX_AVAILABLE_LEVEL:
                    st.session_state.current_level += 1
            else:
                # Store the current level for "try again" scenario
                st.session_state.evaluation_result["failed_level"] = st.session_state.current_level
            
        # Store goal achievement result for display
        st.session_state.evaluation_result["goal_achieved"] = goal_success
        
        # Switch to results page
        st.session_state.current_page = "results"
        st.rerun()
        
    except Exception as e:
        st.error(f"Error during processing: {str(e)}")

def process_email_evaluation_developer_mode(scenario, email_content, model):
    """Process email evaluation using custom settings from developer mode"""
    # Show loading screen with multiple steps
    progress_text = st.empty()
    progress_bar = st.progress(0)
    
    try:
        # Step 1: Load or generate rubric
        progress_text.text("🔄 Loading evaluation rubric...")
        progress_bar.progress(0.25)
        
        rubric_generator = RubricGenerator()
        scenario_filename = st.session_state.get("selected_scenario_file", "")
        
        if scenario_filename:
            rubric = rubric_generator.get_or_generate_rubric(scenario, scenario_filename, model)
        else:
            # Fallback to direct generation if no filename available
            rubric = rubric_generator.generate_rubric(scenario, model)
        
        if not rubric:
            st.error("Failed to generate rubric")
            return
        
        # Step 2: Generate recipient reply
        progress_text.text("📨 Awaiting response from recipient...")
        progress_bar.progress(0.5)
        
        recipient_prompt_value = st.session_state.get("recipient_prompt", "")
        recipient = EmailRecipient()
        recipient_reply = recipient.generate_reply(
            recipient_prompt_value, email_content, model
        )
        
        if not recipient_reply:
            st.error("Failed to generate recipient reply")
            return
        
        # Step 3: Evaluate the email using the generated rubric
        progress_text.text("📊 Evaluating your email...")
        progress_bar.progress(0.75)
        
        evaluator = EmailEvaluator()
        evaluation_result = evaluator.evaluate_email(
            scenario, email_content, rubric, recipient_reply, model
        )
        
        if not evaluation_result:
            st.error("Failed to evaluate email")
            return
        
        # Step 4: Complete
        progress_text.text("✅ Evaluation complete!")
        progress_bar.progress(1.0)
        
        # Store all data for results page
        st.session_state.evaluation_result = {
            "scenario": scenario,
            "email": email_content,
            "rubric": rubric,
            "recipient_reply": recipient_reply,
            "evaluation": evaluation_result,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Switch to results page
        st.session_state.current_page = "results"
        st.rerun()
        
    except Exception as e:
        st.error(f"Error during processing: {str(e)}")

def show_results_page():
    """Show the evaluation results"""
    st.markdown("""
    <style>
    .compact-header h2 {
        margin-top: 0rem !important;
        margin-bottom: 0.5rem !important;
        padding-top: 0rem !important;
    }
    </style>
    <div class="compact-header">
    
    ## 📊 Email Evaluation Results
    
    </div>
    """, unsafe_allow_html=True)
    
    if st.session_state.evaluation_result:
        result = st.session_state.evaluation_result
        
        # Navigation buttons for user mode
        if st.session_state.get("app_mode") == "user":
            col1, col2 = st.columns(2)
            
            with col1:
                # Show "Return to Previous Level" if there is a previous level
                current_level = st.session_state.get("current_level", 1)
                can_go_back = current_level > 1 or len(st.session_state.get("completed_levels", set())) > 0
                
                if can_go_back:
                    previous_level = current_level - 1 if current_level > 1 else max(st.session_state.get("completed_levels", {1}))
                    if st.button(f"← Return to Level {previous_level}", type="secondary"):
                        st.session_state.current_level = previous_level
                        st.session_state.current_page = "game"
                        st.rerun()
                else:
                    st.button("← No Previous Level", disabled=True, type="secondary")
            
            with col2:
                # Show "Advance to Next Level" or "Try Again" based on success
                if "goal_achieved" in result and result["goal_achieved"]:
                    completed_level = result.get("completed_level", current_level)
                    next_level = completed_level + 1
                    
                    if next_level <= MAX_AVAILABLE_LEVEL:
                        if st.button(f"Advance to Level {next_level} →", type="primary"):
                            st.session_state.current_level = next_level
                            st.session_state.current_page = "game"
                            st.rerun()
                    else:
                        st.button("🏆 All Levels Complete!", disabled=True, type="primary")
                else:
                    if st.button(f"Try Level {current_level} Again →", type="primary"):
                        # Go back to current level (which they failed)
                        failed_level = result.get("failed_level", current_level)
                        st.session_state.current_level = failed_level
                        st.session_state.current_page = "game"
                        st.rerun()
        else:
            # Developer mode - keep simple back button
            if st.button("← Back to Game", type="secondary"):
                st.session_state.current_page = "game"
                st.rerun()
        
        # Show goal achievement status and next steps (only for user mode)
        if st.session_state.get("app_mode") == "user" and "goal_achieved" in result:
            if result["goal_achieved"]:
                # Check if user completed all available levels
                completed_count = len(st.session_state.get("completed_levels", set()))
                
                if completed_count >= MAX_AVAILABLE_LEVEL:
                    st.success("🏆 **Congratulations!** You've completed all available levels! You're a master communicator!")
                else:
                    st.success("🎉 **Success!** You persuaded the recipient and advanced to the next level!")
                    
            else:
                st.error("❌ **Goal Not Achieved** - You need to successfully persuade the recipient to advance. Try again with a different approach!")
        
        st.markdown("---")
        
        # Show the scenario
        st.subheader("📋 Scenario")
        st.text_area("", value=result["scenario"], height=200, disabled=True)
        
        # Show the email
        st.subheader("✍️ Your Email")
        st.text_area("", value=result["email"], height=300, disabled=True)
        
        # Show the recipient reply
        if "recipient_reply" in result:
            st.subheader("📨 Recipient's Reply")
            st.markdown(result["recipient_reply"])
        
        # Show the generated rubric (collapsible)
        if "rubric" in result:
            with st.expander("📏 Evaluation Rubric", expanded=False):
                st.markdown(result["rubric"])
        
        # Show the evaluation with improved formatting (collapsible)
        with st.expander("🤖 AI Evaluation", expanded=True):
            st.markdown("""
            <style>
            .quote-box {
                background-color: #fff3cd;
                border: 1px solid #ffeaa7;
                border-radius: 5px;
                padding: 12px;
                margin: 4px 0 24px 0;
                font-style: italic;
                white-space: pre-line;
            }
            .evaluation-content {
                font-size: 0.9rem !important;
                line-height: 1.5 !important;
            }
            .evaluation-content p {
                font-size: 0.9rem !important;
                line-height: 1.5 !important;
                margin-bottom: 1rem !important;
            }
            .evaluation-content ul {
                list-style: none !important;
                padding-left: 0 !important;
            }
            .evaluation-content li {
                margin-bottom: 1rem !important;
                font-size: 0.9rem !important;
            }
            .evaluation-item {
                margin-bottom: 4px;
            }
            .evaluation-item:first-child {
                margin-top: 0;
            }
            </style>
            """, unsafe_allow_html=True)
            
            # Process evaluation to add yellow boxes for quotes/rationales  
            evaluation_text = result["evaluation"]
            
            # Remove bullet points first
            processed_evaluation = re.sub(r'^\s*[-•*]\s*', '', evaluation_text, flags=re.MULTILINE)
            
            # Process evaluation to add yellow boxes for quotes and rationales
            def process_quotes_and_rationales(text):
                lines = text.split('\n')
                # Remove empty lines
                lines = [line for line in lines if line.strip()]
                processed_lines = []

                i = 0
                while i < len(lines):
                    line = lines[i].strip() 

                    if line.startswith('Quote:') or line.startswith('Rationale:'):
                        # Check if there's a next line and if it's a Rationale
                        if i + 1 < len(lines):
                            next_line = lines[i + 1].strip()
                            if next_line.startswith('Rationale:'):
                                line = f'{line}\n\n{next_line.strip()}'
                                i += 1  # Skip the next line since we've processed it
                        
                        processed_lines.append(f'<div class="quote-box">{line.strip()}</div>')
                    elif line:  # Only add non-empty lines
                        processed_lines.append(f'<div class="evaluation-item">{line}</div>')
                    
                    i += 1  # Move to next line
                
                return '\n'.join(processed_lines)
            
            processed_evaluation = process_quotes_and_rationales(processed_evaluation)
            
            st.markdown(f'<div class="evaluation-content">{processed_evaluation}</div>', unsafe_allow_html=True)
        
        st.markdown("---")
        # st.caption(f"Evaluated on {result['timestamp']}")
        
        # Bottom navigation buttons (same as top)
        if st.session_state.get("app_mode") == "user":
            col1, col2 = st.columns(2)
            
            with col1:
                current_level = st.session_state.get("current_level", 1)
                can_go_back = current_level > 1 or len(st.session_state.get("completed_levels", set())) > 0
                
                if can_go_back:
                    previous_level = current_level - 1 if current_level > 1 else max(st.session_state.get("completed_levels", {1}))
                    if st.button(f"← Return to Level {previous_level}", type="secondary", key="back_bottom_prev"):
                        st.session_state.current_level = previous_level
                        st.session_state.current_page = "game"
                        st.rerun()
                else:
                    st.button("← No Previous Level", disabled=True, type="secondary", key="back_bottom_prev_disabled")
            
            with col2:
                if "goal_achieved" in result and result["goal_achieved"]:
                    completed_level = result.get("completed_level", current_level)
                    next_level = completed_level + 1
                    
                    if next_level <= MAX_AVAILABLE_LEVEL:
                        if st.button(f"Advance to Level {next_level} →", type="primary", key="back_bottom_next"):
                            st.session_state.current_level = next_level
                            st.session_state.current_page = "game"
                            st.rerun()
                    else:
                        st.button("🏆 All Levels Complete!", disabled=True, type="primary", key="back_bottom_complete")
                else:
                    if st.button(f"Try Level {current_level} Again →", type="primary", key="back_bottom_retry"):
                        failed_level = result.get("failed_level", current_level)
                        st.session_state.current_level = failed_level
                        st.session_state.current_page = "game"
                        st.rerun()
        else:
            # Developer mode - keep simple back button
            if st.button("← Back to Game", type="secondary", key="back_bottom"):
                st.session_state.current_page = "game"
                st.rerun()
    
    else:
        st.error("No evaluation results found.")
        if st.button("← Back to Game"):
            st.session_state.current_page = "game"
            st.rerun()

def main():
    # Set sidebar state based on mode
    sidebar_state = "expanded" if st.session_state.get("app_mode") == "developer" else "collapsed"
    
    # Set layout based on mode and page
    # Wide layout for developer mode gameplay, centered for everything else
    layout = "wide" if (st.session_state.get("app_mode") == "developer" and 
                       st.session_state.get("current_page") == "game") else "centered"
    
    st.set_page_config(
        page_title="Email.io: Can You Write Better Emails than AI?",
        page_icon="📧",
        layout=layout,
        initial_sidebar_state=sidebar_state,
        menu_items={
            'Get Help': 'https://github.com/your-repo/email-game',
            'Report a bug': 'https://github.com/your-repo/email-game/issues',
            'About': """
            # Email Writing Game
            Practice your email communication skills with AI-powered feedback!
            
            Choose between User Mode (clean interface) or Developer Mode (full controls).
            
            This app helps you improve professional email writing through:
            - Realistic scenarios
            - AI feedback and scoring
            - Recipient response simulation
            
            Built with Streamlit and OpenAI GPT-4o.
            """
        }
    )
    
    # Simple page navigation
    if st.session_state.current_page == "game":
        show_game_page()
    elif st.session_state.current_page == "results":
        show_results_page()
    elif st.session_state.current_page == "mode_selection":
        show_mode_selection_page()
    else:
        # Default to game page
        st.session_state.current_page = "game"
        show_game_page()

if __name__ == "__main__":
    main()