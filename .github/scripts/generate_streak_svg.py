import requests
import json
import sys
import os
from datetime import datetime, date
import svgwrite
import time

# --- 1. API & Data Fetching ---

def get_headers():
    token = os.getenv("GITHUB_TOKEN")
    if not token or len(token) < 10:
        raise ValueError("GITHUB_TOKEN missing or invalid!")
    return {
        'Authorization': f'Bearer {token}',
        'User-Agent': 'Streak-Generator'
    }

def run_graphql_query(query, variables):
    url = "https://api.github.com/graphql"
    response = requests.post(url, json={'query': query, 'variables': variables}, headers=get_headers())
    if response.status_code != 200:
        raise Exception(f"HTTP {response.status_code}: {response.text}")
    data = response.json()
    if 'errors' in data:
        raise Exception(f"GraphQL errors: {json.dumps(data['errors'], indent=2)}")
    return data

def fetch_user_creation_date(username):
    query = """
    query($userName: String!) {
      user(login: $userName) { createdAt }
    }
    """
    data = run_graphql_query(query, {"userName": username})
    user_data = data.get('data', {}).get('user')
    if not user_data:
        raise Exception(f"User '{username}' not found")
    return datetime.fromisoformat(user_data['createdAt'].replace('Z', '+00:00'))

def fetch_contributions_for_year(username, year):
    query = """
    query($userName: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $userName) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays { date contributionCount }
            }
          }
        }
      }
    }
    """
    start_date = f"{year}-01-01T00:00:00Z"
    end_date = f"{year}-12-31T23:59:59Z"
    variables = {"userName": username, "from": start_date, "to": end_date}
    data = run_graphql_query(query, variables)
    return data['data']['user']['contributionsCollection']['contributionCalendar']

def fetch_all_contributions(username):
    created_at = fetch_user_creation_date(username)
    start_year = created_at.year
    current_year = datetime.now().year
    
    total_lifetime = 0
    all_daily_counts = {}

    print(f"Fetching history from {start_year} to {current_year}...")
    for year in range(start_year, current_year + 1):
        calendar = fetch_contributions_for_year(username, year)
        total_lifetime += calendar['totalContributions']
        for week in calendar['weeks']:
            for day in week['contributionDays']:
                count = day['contributionCount']
                if count > 0:
                    all_daily_counts[day['date']] = count
        time.sleep(0.1)

    return all_daily_counts, total_lifetime, created_at

def calculate_streaks(daily_counts):
    if not daily_counts:
        return 0, 0, datetime.now().strftime("%b %d, %Y")

    dates = sorted(daily_counts.keys())
    today = datetime.now().date()
    
    # Current Streak
    current_streak = 0
    last_contribution_date_str = dates[-1]
    last_contribution_date = datetime.strptime(last_contribution_date_str, '%Y-%m-%d').date()
    diff = (today - last_contribution_date).days
    
    if diff <= 1:
        current_streak = 1
        check_date = last_contribution_date
        for i in range(len(dates) - 2, -1, -1):
            prev_date = datetime.strptime(dates[i], '%Y-%m-%d').date()
            if (check_date - prev_date).days == 1:
                current_streak += 1
                check_date = prev_date
            else:
                break
    
    # Longest Streak
    longest_streak = 0
    current_count = 0
    prev_date = None
    longest_start_date = None
    longest_end_date = None
    temp_start = None

    for date_str in dates:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        if prev_date and (date_obj - prev_date).days == 1:
            current_count += 1
        else:
            current_count = 1
            temp_start = date_obj
            
        if current_count > longest_streak:
            longest_streak = current_count
            longest_start_date = temp_start
            longest_end_date = date_obj
        prev_date = date_obj

    if longest_start_date and longest_end_date:
        s_fmt = longest_start_date.strftime("%b %d, %Y")
        e_fmt = longest_end_date.strftime("%b %d, %Y")
        longest_range_str = f"{s_fmt} - {e_fmt}"
    else:
        longest_range_str = "N/A"

    return current_streak, longest_streak, longest_range_str

# --- 2. SVG Generation Logic ---

def generate_svg(filename, theme, current, longest, total, longest_range, start_date_obj):
    """Generates an SVG for a specific theme configuration."""
    
    formatted_start_date = start_date_obj.strftime("%b %d, %Y")
    lifetime_label = f"{formatted_start_date} - Present"
    
    dwg = svgwrite.Drawing(filename, size=('495px', '195px'), viewBox='0 0 495 195')

    # CSS with Media Queries
    css_styles = f"""
        @keyframes currstreak {{
            0% {{ font-size: 3px; opacity: 0.2; }}
            80% {{ font-size: 34px; opacity: 1; }}
            100% {{ font-size: 28px; opacity: 1; }}
        }}
        @keyframes fadein {{
            0% {{ opacity: 0; }}
            100% {{ opacity: 1; }}
        }}
        
        /* LIGHT MODE (Default) */
        .bg {{ fill: {theme['light']['bg']}; stroke: {theme['light']['border']}; }}
        .divider {{ stroke: {theme['light']['border']}; }}
        .text-accent {{ fill: {theme['light']['accent']}; font-family: 'Segoe UI', Ubuntu, sans-serif; font-weight: 700; font-size: 28px; }}
        .text-label {{ fill: {theme['light']['label']}; font-family: 'Segoe UI', Ubuntu, sans-serif; font-size: 14px; }}
        .text-range {{ fill: {theme['light']['range']}; font-family: 'Segoe UI', Ubuntu, sans-serif; font-size: 12px; }}
        .text-current {{ fill: {theme['light']['current']}; font-family: 'Segoe UI', Ubuntu, sans-serif; font-weight: 700; font-size: 28px; }}
        .ring {{ stroke: {theme['light']['accent']}; }}
        .fire {{ fill: {theme['light']['fire']}; }}
        
        /* DARK MODE */
        @media (prefers-color-scheme: dark) {{
            .bg {{ fill: {theme['dark']['bg']}; stroke: {theme['dark']['border']}; }}
            .divider {{ stroke: {theme['dark']['border']}; }}
            .text-accent {{ fill: {theme['dark']['accent']}; }}
            .text-label {{ fill: {theme['dark']['label']}; }}
            .text-range {{ fill: {theme['dark']['range']}; }}
            .text-current {{ fill: {theme['dark']['current']}; }}
            .ring {{ stroke: {theme['dark']['accent']}; }}
            .fire {{ fill: {theme['dark']['fire']}; }}
        }}
    """
    dwg.defs.add(dwg.style(css_styles))

    # Shapes
    clip = dwg.clipPath(id='outer_rectangle')
    clip.add(dwg.rect(insert=(0, 0), size=(495, 195), rx=4.5))
    dwg.defs.add(clip)

    mask = dwg.mask(id='mask_out_ring_behind_fire')
    mask.add(dwg.rect(insert=(0, 0), size=(495, 195), fill='white'))
    mask.add(dwg.ellipse(center=(247.5, 32), r=(13, 18), fill='black'))
    dwg.defs.add(mask)

    main = dwg.g(clip_path='url(#outer_rectangle)')
    dwg.add(main)

    # Elements
    main.add(dwg.rect(insert=(0.5, 0.5), size=(494, 194), rx=4.5, class_="bg"))
    main.add(dwg.line(start=(165, 28), end=(165, 170), stroke_width=1, class_="divider"))
    main.add(dwg.line(start=(330, 28), end=(330, 170), stroke_width=1, class_="divider"))

    # Text Elements
    # Left
    main.add(dwg.text(str(total), insert=(82.5, 80), text_anchor='middle', class_="text-accent", style='opacity: 0; animation: fadein 0.5s linear forwards 0.6s'))
    main.add(dwg.text('Total Contributions', insert=(82.5, 116), text_anchor='middle', class_="text-label", style='opacity: 0; animation: fadein 0.5s linear forwards 0.7s'))
    main.add(dwg.text(lifetime_label, insert=(82.5, 146), text_anchor='middle', class_="text-range", style='opacity: 0; animation: fadein 0.5s linear forwards 0.8s'))

    # Center
    main.add(dwg.text('Current Streak', insert=(247.5, 140), text_anchor='middle', class_="text-current", style='opacity: 0; animation: fadein 0.5s linear forwards 0.9s; font-size: 14px;'))
    main.add(dwg.text(datetime.now().strftime("%b %d"), insert=(247.5, 166), text_anchor='middle', class_="text-range", style='opacity: 0; animation: fadein 0.5s linear forwards 0.9s'))
    
    # Ring & Flame
    ring_g = dwg.g(mask='url(#mask_out_ring_behind_fire)')
    ring_g.add(dwg.circle(center=(247.5, 71), r=40, fill='none', stroke_width=5, class_="ring", style='opacity: 0; animation: fadein 0.5s linear forwards 0.4s'))
    main.add(ring_g)
    
    flame_g = dwg.g(transform='translate(247.5, 19.5)', style='opacity: 0; animation: fadein 0.5s linear forwards 0.6s')
    flame_g.add(dwg.path(d="M -12 -0.5 L 15 -0.5 L 15 23.5 L -12 23.5 L -12 -0.5 Z", fill='none'))
    flame_g.add(dwg.path(d="M 1.5 0.67 C 1.5 0.67 2.24 3.32 2.24 5.47 C 2.24 7.53 0.89 9.2 -1.17 9.2 C -3.23 9.2 -4.79 7.53 -4.79 5.47 L -4.76 5.11 C -6.78 7.51 -8 10.62 -8 13.99 C -8 18.41 -4.42 22 0 22 C 4.42 22 8 18.41 8 13.99 C 8 8.6 5.41 3.79 1.5 0.67 Z M -0.29 19 C -2.07 19 -3.51 17.6 -3.51 15.86 C -3.51 14.24 -2.46 13.1 -0.7 12.74 C 1.07 12.38 2.9 11.53 3.92 10.16 C 4.31 11.45 4.51 12.81 4.51 14.2 C 4.51 16.85 2.36 19 -0.29 19 Z", class_="fire"))
    main.add(flame_g)
    
    main.add(dwg.text(str(current), insert=(247.5, 80), text_anchor='middle', class_="text-current", style='animation: currstreak 0.6s linear forwards'))

    # Right
    main.add(dwg.text(str(longest), insert=(412.5, 80), text_anchor='middle', class_="text-accent", style='opacity: 0; animation: fadein 0.5s linear forwards 1.2s'))
    main.add(dwg.text('Longest Streak', insert=(412.5, 116), text_anchor='middle', class_="text-label", style='opacity: 0; animation: fadein 0.5s linear forwards 1.3s'))
    main.add(dwg.text(longest_range, insert=(412.5, 146), text_anchor='middle', class_="text-range", style='opacity: 0; animation: fadein 0.5s linear forwards 1.4s'))

    dwg.save()
    print(f"Saved: {filename}")

# --- 3. Main Execution ---

if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise ValueError("Provide username as first argument")
    
    username = sys.argv[1].strip()
    print(f"User: {username}")
    
    # 1. Fetch Data ONCE
    daily_counts, total, created_at_date = fetch_all_contributions(username)
    current, longest, longest_range = calculate_streaks(daily_counts)
    
    # 2. Define Themes
    themes_config = {
        "ocean": {
            "light": {"bg": "#F8FAFC", "border": "#CBD5E1", "accent": "#3B82F6", "current": "#8B5CF6", "label": "#1D4ED8", "range": "#10B981", "fire": "#3B82F6"},
            "dark":  {"bg": "#1A1B27", "border": "#E4E2E2", "accent": "#5B9EFF", "current": "#A78BFA", "label": "#5B9EFF", "range": "#34D399", "fire": "#5B9EFF"}
        },
        "forest": {
            "light": {"bg": "#F8FAFC", "border": "#CBD5E1", "accent": "#10B981", "current": "#059669", "label": "#047857", "range": "#F59E0B", "fire": "#10B981"},
            "dark":  {"bg": "#1A1B27", "border": "#E4E2E2", "accent": "#10B981", "current": "#34D399", "label": "#10B981", "range": "#FBBF24", "fire": "#10B981"}
        },
        "github": {
            "light": {"bg": "#FFFFFF", "border": "#D0D7DE", "accent": "#0969DA", "current": "#0969DA", "label": "#57606A", "range": "#57606A", "fire": "#D95641"},
            "dark":  {"bg": "#0D1117", "border": "#30363D", "accent": "#58A6FF", "current": "#58A6FF", "label": "#8B949E", "range": "#8B949E", "fire": "#D95641"}
        }
    }
    
    # 3. Generate All Files
    os.makedirs('assets/Streaks', exist_ok=True)
    
    for key, theme in themes_config.items():
        filename = f"assets/Streaks/streak-{key}.svg"
        generate_svg(filename, theme, current, longest, total, longest_range, created_at_date)
        
    print("All themes generated successfully!")
