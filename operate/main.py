"""
Self Driving Computer
"""
import os
import time
import base64
import json
import math


from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import message_dialog
from prompt_toolkit.styles import Style as PromptStyle
from prompt_toolkit.formatted_text import HTML
from colorama import Style as ColoramaStyle
from dotenv import load_dotenv
from PIL import ImageGrab, Image, ImageDraw, ImageFont
import matplotlib.font_manager as fm
import pyautogui
import subprocess
import os

from openai import OpenAI

load_dotenv()

DEBUG = False
WITH_REFLECTION = False

client = OpenAI()
client.api_key = os.getenv("OPENAI_API_KEY")


tools = [
    {
        "type": "function",
        "function": {
            "name": "mouse_click",
            "description": "This function clicks fields, buttons, and windows on the screen.",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "A description of the click location.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "keyboard_type",
            "description": "This function types the specified text on the keyboard.",
            "parameters": {
                "type": "object",
                "properties": {
                    "type_value": {
                        "type": "string",
                        "description": "The text to type on the keyboard.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mac_search",
            "description": "This function searches on Mac for programs",
            "parameters": {
                "type": "object",
                "properties": {
                    "type_value": {
                        "type": "string",
                        "description": "The text to do on Mac search.",
                    },
                },
            },
        },
    },
]


MOUSE_PROMPT = """
From looking at a screenshot, your goal is to guess the X & Y location of a window or field on the screen in order to fire a click event. The X & Y location are in percentage (%) of screen width and height.

Your job is to click on windows or fields that will progress you towards your objective. The screenshot has a grid with percentages to help you guess the X & Y location. 

Example are below.
__
Objective: Find a image of a banana
Click: {{ "x": "50%", "y": "60%", "explanation": "I can see a Google Search field, I'm going to click that so I can search." }} 
__
Objective: Open Spotify and play the beatles
Click: {{ "x": "20%", "y": "92%", "explanation": "Spotify is open I'll click the search field to look for the beatles." }}
__

I'm sure you know this but, the left side of the screen will have a x % value lower than 50% and the right side will have x% value higher than 50%. 

A few important notes: 
- Use grid with percentages as a guide to guess the X & Y location, but avoid clicking exactly at the grid cross hairs since they are unlikely to be the exact location.
- When opening Google Chrome if you see profile buttons, click the profile button at the following location {{ "x": "50%", "y": "55%" }} to fully open Chrome.
- The address bar for Chrome while in full screen is around {{ "x": "50%", "y": "8%" }}.

IMPORTANT: Always respond with the correct following format: 
{{ "x": "percent", "y": "percent", "explanation": "~explanation detail~" }} 

Objective: {objective}
Click:
"""

VISION_PROMPT = """
From looking at a screenshot, the objective and you previous steps, your goal is to take the best next action to reach the objective. 

To complete emulate a human operator you only need three actions. These are the actions available to you below. 

1. CLICK - Move mouse and click
2. TYPE - Type on the keyboard
3. SEARCH - Search for a program on Mac and open it

Here are your formats for how to respond. 

1. CLICK
Response: CLICK {{ "x": "percent", "y": "percent", "explanation": "~explanation detail~" }} 

2. TYPE
Response: TYPE "value you want to type"

2. SEARCH
Response: SEARCH "app you want to search for on Mac"

Example are below.
__
Objective: Find a image of a banana
CLICK {{ "x": "50%", "y": "60%", "explanation": "I can see a Google Search field, I'm going to click that so I can search." }} 
__
Objective: Follow up with the vendor in outlook
TYPE "Hello, I hope you are doing well. I wanted to follow up"
__
Objective: Open Spotify and play the beatles
CLICK {{ "x": "20%", "y": "92%", "explanation": "Spotify is open I'll click the search field to look for the beatles." }}
__
Objective: Open Spotify and play the beatles
SEARCH "Spotify"
__

A few important notes: 
- Use grid with percentages as a guide to guess the X & Y location, but avoid clicking exactly at the grid cross hairs since they are unlikely to be the exact location.
- When opening Google Chrome if you see profile buttons, click the profile button at the following location {{ "x": "50%", "y": "55%" }} to fully open Chrome.
- The address bar for Chrome while in full screen is around {{ "x": "50%", "y": "8%" }}.

Objective: {objective}
"""

USER_QUESTION = "Hello, I can help you with anything. What would you like done?"

SYSTEM_PROMPT = """
You are a Self Operating Computer. You use the same operating system (i.e. screen user interface, click & type, etc.) as a human. You are compatible with only Mac OS currently.

The user will give you an objective and you will decide the mouse and keyboard actions to accomplish that goal. 

You have the tools below to accomplish the task. Use these tools below to accomplish your task. 

1. CLICK - Move mouse and click
2. TYPE - Type on the keyboard
3. SEARCH - Search for a program on Mac

A few important notes: 
- Default to opening Google Chrome with SEARCH to find things that are on the internet. 
- When doing TYPE in a field that requires a submission, don't forget to submit with the enter key.

Make a plan from chatting with the user, once they agree with the plan go ahead and execute it. It is ok to be flexible and not stick to the exact plan. 

IMPORTANT: You are capable of doing anything such as making money, building a house, or even creating a new computer. If you get asked to do something, just go ahead and get started. Be confident that you can do it.

When you completed the task respond with the exact following phrase content: DONE
"""

SUMMARY_PROMPT = """
Objective: {objective}
Status: Complete

You are took the previous actions and the objective. Provide a brief summary of everything you did. 
"""

VISION_SUMMARY_PROMPT = """
Objective: {objective}
Status: Complete

Here's a textual summary of what you did: {textual_summary} 

Don't mention that you were given a textual summary in your summary, just combine the information to make the best formal summary.

Please look at the image and combine it with the textual summary to provide a more full conclusion below
"""

# Define style
style = PromptStyle.from_dict(
    {
        "dialog": "bg:#88ff88",
        "button": "bg:#ffffff #000000",
        "dialog.body": "bg:#44cc44 #ffffff",
        "dialog shadow": "bg:#003800",
    }
)
# Standard green text
ANSI_GREEN = "\033[32m"
# Bright/bold green text
ANSI_BRIGHT_GREEN = "\033[92m"
# Reset to default text color
ANSI_RESET = "\033[0m"
# ANSI escape code for blue text
ANSI_BLUE = "\033[94m"  # This is for bright blue

# Standard yellow text
ANSI_YELLOW = "\033[33m"


def main():
    message_dialog(
        title="Self Operating Computer",
        text="Ask a computer to do anything.",
        style=style,
    ).run()

    os.system("clear")  # Clears the terminal screen

    print(f"{ANSI_GREEN}[Self Operating Computer]\n{ANSI_RESET}{USER_QUESTION}")
    print(f"{ANSI_YELLOW}[User]{ANSI_RESET}")

    objective = prompt(
        style=style,
    )

    system_prompt = {"role": "system", "content": SYSTEM_PROMPT}
    assistant_message = {"role": "assistant", "content": USER_QUESTION}
    user_message = {
        "role": "user",
        "content": objective,  # we need to change this to allow messages.
    }
    messages = [system_prompt, assistant_message, user_message]

    looping = True
    loop_count = 0

    while looping:
        if DEBUG:
            print("[loop] messages before next action:\n\n\n", messages[1:])
        response = get_next_action(messages, objective)

        # tool_calls = response.tool_calls
        # messages.append(response)

        # if tool_calls:
        #     for tool_call in tool_calls:
        #         function_name = tool_call.function.name

        #         function_args = json.loads(tool_call.function.arguments)

        #         print(
        #             f"{ANSI_GREEN}[Self Operating Computer][Use Tool]\n{ANSI_RESET}{function_name}"
        #         )
        #         print(
        #             f"{ANSI_GREEN}[Self Operating Computer][Use Tool] with\n{ANSI_RESET}{function_args}"
        #         )

        #         if function_name == "mouse_click":
        #             function_response = mouse_click(
        #                 objective, function_args["description"]
        #             )

        #         elif function_name == "keyboard_type":
        #             function_response = keyboard_type(function_args["type_value"])
        #         else:
        #             function_response = mac_search(function_args["type_value"])
        #         print(
        #             f"{ANSI_GREEN}[Self Operating Computer][Use Tool] response\n{ANSI_RESET}{function_response}"
        #         )
        #         messages.append(
        #             {
        #                 "tool_call_id": tool_call.id,
        #                 "role": "tool",
        #                 "name": function_name,
        #                 "content": function_response,
        #             }
        #         )
        #         if WITH_REFLECTION:
        #             reflection = reflect(objective, function_name, function_response)
        #             messages.append(
        #                 {
        #                     "role": "assistant",
        #                     "content": reflection,
        #                 }
        #             )

        # else:
        #     if response.content == "DONE":
        #         print(
        #             f"{ANSI_GREEN}[Self Operating Computer]{ANSI_BLUE} Objective complete {ANSI_RESET}"
        #         )
        #         looping = False
        #         summary = summarize(messages, objective)
        #         print(
        #             f"{ANSI_GREEN}[Self Operating Computer]{ANSI_BLUE} Summary\n{ANSI_RESET}{summary}"
        #         )

        #         break

        #     print(
        #         f"{ANSI_GREEN}[Self Operating Computer]\n{ANSI_RESET}{response.content}"
        #     )
        #     print(f"{ANSI_YELLOW}[User]{ANSI_RESET}")

        #     new_user_response = prompt(style=style)
        #     messages.append(
        #         {
        #             "role": "user",
        #             "content": new_user_response,
        #         }
        #     )

        # loop_count += 1
        # if loop_count > 10:
        looping = False


def format_mouse_prompt(objective):
    prompt = MOUSE_PROMPT.format(objective=objective)
    if DEBUG:
        print("[format_mouse_prompt] prompt", prompt)

    return prompt


def format_summary_prompt(objective):
    return SUMMARY_PROMPT.format(objective=objective)


def format_vision_summary_prompt(objective, textual_summary):
    return VISION_SUMMARY_PROMPT.format(
        objective=objective, textual_summary=textual_summary
    )


def format_vision_prompt(objective):
    prompt = VISION_PROMPT.format(objective=objective)
    if DEBUG:
        print("[format_vision_prompt] prompt", prompt)

    return prompt


# def get_next_action(messages):
#     response = client.chat.completions.create(
#         model="gpt-4",
#         messages=messages,
#         tools=tools,
#         tool_choice="auto",  # auto is default, but we'll be explicit
#     )

#     return response.choices[0].message


def get_next_action(messages, objective):
    try:
        screenshot_filename = "screenshots/screenshot.png"
        # Call the function to capture the screen with the cursor
        capture_screen_with_cursor(screenshot_filename)

        new_screenshot_filename = "screenshots/screenshot_with_grid.png"

        add_grid_to_image(screenshot_filename, new_screenshot_filename, 650)

        with open(new_screenshot_filename, "rb") as img_file:
            img_base64 = base64.b64encode(img_file.read()).decode("utf-8")

        vision_prompt = format_vision_prompt(objective)

        vision_message = {
            "role": "user",
            "content": [
                {"type": "text", "text": vision_prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"},
                },
            ],
        }
        messages.append(vision_message)

        response = client.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=messages,
            max_tokens=300,
        )

        response = response.choices[0]
        print("[get_next_action] response", response)
        content = result.message.content
        print("[get_next_action] content", content)

        # parsed_result = extract_json_from_string(content)
        # print(
        #     f"{ANSI_GREEN}[Self Operating Computer][Use Tool] click\n{ANSI_RESET}{parsed_result}"
        # )
        # x = convert_percent_to_decimal(parsed_result["x"])
        # y = convert_percent_to_decimal(parsed_result["y"])

        # if parsed_result and isinstance(x, float) and isinstance(y, float):
        #     click_at_percentage(x, y)
        #     return content

        # return "We failed to click"

    except Exception as e:
        print(f"Error parsing JSON: {e}")
        return "Failed take action after looking at the screenshot"


def summarize(messages, objective):
    summary_prompt = format_summary_prompt(objective)

    messages.append({"role": "user", "content": summary_prompt})

    response = client.chat.completions.create(
        model="gpt-4",
        messages=messages,
    )

    result = response.choices[0]
    textual_summary = result.message.content
    if DEBUG:
        print("[summarize] textual_summary", textual_summary)

    screenshot_filename = "screenshots/summary_screenshot.png"
    # Call the function to capture the screen with the cursor
    capture_screen_with_cursor(screenshot_filename)

    with open(screenshot_filename, "rb") as img_file:
        img_base64 = base64.b64encode(img_file.read()).decode("utf-8")

    vision_summary_prompt = format_vision_summary_prompt(objective, textual_summary)

    response = client.chat.completions.create(
        model="gpt-4-vision-preview",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": vision_summary_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"},
                    },
                ],
            }
        ],
        max_tokens=300,
    )

    result = response.choices[0]
    content = result.message.content

    return content


def click_at_percentage(
    x_percentage, y_percentage, duration=0.2, circle_radius=50, circle_duration=0.5
):
    # Get the size of the primary monitor
    screen_width, screen_height = pyautogui.size()

    # Calculate the x and y coordinates in pixels
    x_pixel = int(screen_width * float(x_percentage))
    y_pixel = int(screen_height * float(y_percentage))

    # Move to the position smoothly
    pyautogui.moveTo(x_pixel, y_pixel, duration=duration)

    # Circular movement
    start_time = time.time()
    while time.time() - start_time < circle_duration:
        angle = ((time.time() - start_time) / circle_duration) * 2 * math.pi
        x = x_pixel + math.cos(angle) * circle_radius
        y = y_pixel + math.sin(angle) * circle_radius
        pyautogui.moveTo(x, y, duration=0.1)

    # Finally, click
    pyautogui.click(x_pixel, y_pixel)
    return "successfully clicked"


def mouse_click(objective, click_information):
    screenshot_filename = "screenshots/screenshot.png"
    # Call the function to capture the screen with the cursor
    capture_screen_with_cursor(screenshot_filename)

    new_screenshot_filename = "screenshots/screenshot_with_grid.png"

    add_grid_to_image(screenshot_filename, new_screenshot_filename, 650)

    with open(new_screenshot_filename, "rb") as img_file:
        img_base64 = base64.b64encode(img_file.read()).decode("utf-8")

    click_prompt = format_mouse_prompt(objective)

    response = client.chat.completions.create(
        model="gpt-4-vision-preview",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": click_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"},
                    },
                ],
            }
        ],
        max_tokens=300,
    )

    result = response.choices[0]
    content = result.message.content
    if DEBUG:
        print("[mouse_click] content", content)

    try:
        parsed_result = extract_json_from_string(content)
        print(
            f"{ANSI_GREEN}[Self Operating Computer][Use Tool] click\n{ANSI_RESET}{parsed_result}"
        )
        x = convert_percent_to_decimal(parsed_result["x"])
        y = convert_percent_to_decimal(parsed_result["y"])

        if parsed_result and isinstance(x, float) and isinstance(y, float):
            click_at_percentage(x, y)
            return content

        return "We failed to click"

    except Exception as e:
        print(f"Error parsing JSON: {e}")
        return "We failed to click"


def reflect(objective, last_action, last_action_response):
    print("[reflect] last_action_response", last_action_response)
    # sleep for half a second
    time.sleep(0.5)

    screenshot_filename = "screenshots/reflection_screenshot.png"
    # Call the function to capture the screen with the cursor
    capture_screen_with_cursor(screenshot_filename)

    new_screenshot_filename = "screenshots/grid_reflection_screenshot.png"

    add_grid_to_image(screenshot_filename, new_screenshot_filename, 650)

    with open(new_screenshot_filename, "rb") as img_file:
        img_base64 = base64.b64encode(img_file.read()).decode("utf-8")

    reflect_prompt = format_reflection_prompt(
        objective, last_action, last_action_response
    )
    print("[reflect] reflect_prompt", reflect_prompt)
    # import pdb

    # pdb.set_trace()

    response = client.chat.completions.create(
        model="gpt-4-vision-preview",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": reflect_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"},
                    },
                ],
            }
        ],
        max_tokens=300,
    )

    result = response.choices[0]
    content = result.message.content

    print(f"{ANSI_GREEN}[Self Operating Computer][Reflection] {ANSI_RESET} {content}")

    return content


def add_grid_to_image(original_image_path, new_image_path, grid_interval):
    # Load the image
    image = Image.open(original_image_path)

    # Create a drawing object
    draw = ImageDraw.Draw(image)

    # Get the image size
    width, height = image.size

    # Get the path to a TrueType font included with matplotlib
    font_paths = fm.findSystemFonts(fontpaths=None, fontext="ttf")
    # Filter for specific font name (e.g., 'Arial.ttf')
    font_path = next((path for path in font_paths if "Arial" in path), None)
    if not font_path:
        raise RuntimeError(
            "Specific TrueType font not found; install the font or check the font name."
        )

    # Reduce the font size a bit
    font_size = int(grid_interval / 10)  # Reduced font size
    font = ImageFont.truetype(font_path, size=font_size)

    # Calculate the background size based on the font size
    bg_width = int(font_size * 4)  # Adjust as necessary
    bg_height = int(font_size * 1.2)  # Adjust as necessary

    # Function to draw text with a white rectangle background
    def draw_label_with_background(position, text, draw, font, bg_width, bg_height):
        # Adjust the position based on the background size
        text_position = (position[0] + bg_width // 2, position[1] + bg_height // 2)
        # Draw the text background
        draw.rectangle(
            [position[0], position[1], position[0] + bg_width, position[1] + bg_height],
            fill="white",
        )
        # Draw the text
        draw.text(text_position, text, fill="black", font=font, anchor="mm")

    # Draw vertical lines and labels at every `grid_interval` pixels
    for x in range(grid_interval, width, grid_interval):
        line = ((x, 0), (x, height))
        draw.line(line, fill="blue")
        for y in range(grid_interval, height, grid_interval):
            # Calculate the percentage of the width and height
            x_percent = round((x / width) * 100)
            y_percent = round((y / height) * 100)
            draw_label_with_background(
                (x - bg_width // 2, y - bg_height // 2),
                f"{x_percent}%,{y_percent}%",
                draw,
                font,
                bg_width,
                bg_height,
            )

    # Draw horizontal lines - labels are already added with vertical lines
    for y in range(grid_interval, height, grid_interval):
        line = ((0, y), (width, y))
        draw.line(line, fill="blue")

    # Save the image with the grid
    image.save(new_image_path)


def keyboard_type(text):
    for char in text:
        pyautogui.write(char)
    return "successfully typed " + text


def mac_search(text):
    # Press and release Command and Space separately
    pyautogui.keyDown("command")
    pyautogui.press("space")
    pyautogui.keyUp("command")
    # Now type the text
    for char in text:
        pyautogui.write(char)

    pyautogui.press("enter")
    return "successfully opened " + text + " on Mac"


available_functions = {
    "mouse_click": mouse_click,
    "keyboard_type": keyboard_type,
    "mac_search": mac_search,
}  # only one function in this example, but you can have multiple


def capture_screen_with_cursor(file_path="screenshot/screenshot_with_cursor.png"):
    # Use the screencapture utility to capture the screen with the cursor
    subprocess.run(["screencapture", "-C", file_path])


def extract_json_from_string(s):
    # print("extracting json from string", s)
    try:
        # Find the start of the JSON structure
        json_start = s.find("{")
        if json_start == -1:
            return None

        # Extract the JSON part and convert it to a dictionary
        json_str = s[json_start:]
        return json.loads(json_str)
    except Exception as e:
        print(f"Error parsing JSON: {e}")
        return None


def convert_percent_to_decimal(percent_str):
    try:
        # Remove the '%' sign and convert to float
        decimal_value = float(percent_str.strip("%"))

        # Convert to decimal (e.g., 20% -> 0.20)
        return decimal_value / 100
    except ValueError as e:
        print(f"Error converting percent to decimal: {e}")
        return None


if __name__ == "__main__":
    main()
