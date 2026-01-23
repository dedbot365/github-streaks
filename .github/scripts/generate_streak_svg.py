import requests
import sys
import svgwrite
import os
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta  # pip install python-dateutil (but it's often pre-installed; if not, add to workflow)

import requests
import json
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

def fetch_contributions(username):
    """Fetch contribution calendar data using GitHub GraphQL API."""
    query = """
    query($userName: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $userName) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
              }
            }
          }
        }
      }
    }
    """

    to_date = datetime.utcnow()
    from_date = to_date - timedelta(days=365)  # Fixed: exactly 365 days

    variables = {
        "userName": username,
        "from": from_date.isoformat() + "Z",
        "to": to_date.isoformat() + "Z"
    }

    token = os.getenv("GITHUB_TOKEN")
    if not token or len(token) < 10:
        raise ValueError("GITHUB_TOKEN environment variable is missing or invalid!")
    print(f"DEBUG: Token prefix = {token[:4]}... (length: {len(token)})")

    headers = {
        'Authorization': f'Bearer {token}',
        'User-Agent': 'Streak-Stats-Generator'
    }

    url = "https://api.github.com/graphql"
    response = requests.post(url, json={'query': query, 'variables': variables}, headers=headers)

    if response.status_code != 200:
        raise Exception(f"GraphQL HTTP error: {response.status_code} - {response.text}")

    data = response.json()
    if 'errors' in data:
        raise Exception(f"GraphQL errors: {json.dumps(data['errors'], indent=2)}")

    user_data = data.get('data', {}).get('user')
    if not user_data:
        raise Exception(f"User '{username}' not found or no contribution data available")

    calendar = user_data['contributionsCollection']['contributionCalendar']
    total_contribs = calendar['totalContributions']

    daily_counts = {}
    for week in calendar['weeks']:
        for day in week['contributionDays']:
            count = day['contributionCount']
            if count > 0:
                date_str = day['date'][:10]  # YYYY-MM-DD
                daily_counts[date_str] = count

    return daily_counts, total_contribs
def calculate_streaks(daily_counts):
    """Calculate current streak, longest streak, and total contributions."""
    dates = sorted(daily_counts.keys())
    if not dates:
        return 0, 0, 0
    
    total_contribs = sum(daily_counts.values())
    
    # Current streak
    current = 0
    last_date = datetime.now().date()
    for date_str in reversed(dates):
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        if (last_date - date).days == 1 or date == last_date:
            current += 1
            last_date = date
        elif (last_date - date).days > 1:
            break
    
    # Longest streak
    longest = 0
    streak = 0
    prev_date = None
    for date_str in sorted(dates):
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        if prev_date is None or (date - prev_date).days == 1:
            streak += 1
            longest = max(longest, streak)
        else:
            streak = 1
        prev_date = date
    
    return current, longest, total_contribs

def generate_svg(current_streak, longest_streak, total_contribs, username):

    # Use 'full' profile + disable debug/validation
    dwg = svgwrite.Drawing('assets/streak.svg', size=('400px', '160px'),
                           profile='full', debug=False)

    # Background (dark gradient) - unchanged
    dwg.add(dwg.rect(insert=(0, 0), size=('100%', '100%'), rx=12, ry=12,
                     fill='url(#bgGrad)'))

    bg_grad = dwg.linearGradient(start=(0, 0), end=(0, '100%'),
                                 id='bgGrad', gradientUnits='userSpaceOnUse')
    bg_grad.add_stop_color(offset=0, color='#161b22')
    bg_grad.add_stop_color(offset=1, color='#0d1117')
    dwg.defs.add(bg_grad)

    # Title - unchanged
    dwg.add(dwg.text('GitHub Streak', insert=(200, 25), fill='#7dd3fc',
                     font_family='sans-serif', font_size=20,
                     font_weight='bold', text_anchor='middle'))

    # Flame icon - this path should now pass
    flame_path = 'M12 2C13.1 2 14 2.9 14 4c0 1-1.1 2.1-2 3-1 .9-2 0-2 0-1-.9-2-2.1-2-3 0-1.1.9-2 2-2zm0 24c-1.1 0-2-.9-2-2 0-1.1.9-2 2-2s2 .9 2 2c0 1.1-.9 2-2 2zM12 12c-2.2 0-4 1.8-4 4s1.8 4 4 4 4-1.8 4-4-1.8-4-4-4z'
    flame_group = dwg.g(transform='scale(0.05) translate(100, 50)', fill='#f59e0b')
    flame_group.add(dwg.path(d=flame_path, transform='scale(20) translate(5, 2)'))
    dwg.add(flame_group)

    # ... rest of your stats text, username footer, optional bars ...

    os.makedirs('assets', exist_ok=True)
    dwg.save()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise ValueError("Username (repository owner) must be provided as first argument")

    username = sys.argv[1].strip()
    print(f"Generating streak stats for GitHub user: {username}")

    token = os.getenv("GITHUB_TOKEN")
    if not token or len(token) < 10:
        raise ValueError("GITHUB_TOKEN environment variable is missing or invalid!")
    print(f"DEBUG: Token prefix = {token[:4]}... (length: {len(token)})")

    daily_counts, total_contribs = fetch_contributions(username)
    current, longest, _ = calculate_streaks(daily_counts)
    generate_svg(current, longest, total_contribs, username)
    print(f"Generated SVG: Current={current}, Longest={longest}, Total={total_contribs}")
