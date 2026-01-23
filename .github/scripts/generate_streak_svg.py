import requests
import json
import sys
import os
from datetime import datetime, timedelta
import svgwrite

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
    from_date = to_date - timedelta(days=365)

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
    """Calculate current streak and longest streak."""
    if not daily_counts:
        return 0, 0

    dates = sorted(daily_counts.keys())

    # Current streak
    current = 0
    today = datetime.utcnow().date()
    for date_str in reversed(dates):
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        delta = (today - date).days
        if delta <= current:
            current += 1
        else:
            break

    # Longest streak
    longest = 0
    streak = 0
    prev = None
    for date_str in dates:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        if prev is None or (date - prev).days == 1:
            streak += 1
            longest = max(longest, streak)
        else:
            streak = 1
        prev = date

    return current, longest


def generate_svg(current, longest, total, username):
    dwg = svgwrite.Drawing('assets/streak.svg', size=('520px', '220px'),
                           profile='full', debug=False)

    # Background gradient
    dwg.add(dwg.rect(insert=(0, 0), size=('100%', '100%'), rx=16, ry=16,
                     fill='url(#bg)'))

    bg = dwg.linearGradient(start=(0, 0), end=(0, '100%'), id='bg')
    bg.add_stop_color(offset=0, color='#0f1117')
    bg.add_stop_color(offset=1, color='#161b22')
    dwg.defs.add(bg)

    # Glow filter – built step by step to avoid constructor issues
    glow = dwg.filter(id='glow', x='-50%', y='-50%', width='200%', height='200%')
    glow.add(dwg.feGaussianBlur(stdDeviation=2.5, result='blur'))

    fe_merge = dwg.feMerge()
    fe_merge.add(dwg.feMergeNode(in_='blur'))
    fe_merge.add(dwg.feMergeNode(in_='SourceGraphic'))
    glow.add(fe_merge)
    dwg.defs.add(glow)

    # Flame gradient
    flame_grad = dwg.linearGradient(start=(0, 0), end=(0, '100%'), id='flameGrad')
    flame_grad.add_stop_color(offset=0,    color='#fff176')  # yellow
    flame_grad.add_stop_color(offset=0.4,  color='#ff9800')  # orange
    flame_grad.add_stop_color(offset=0.7,  color='#f44336')  # red
    flame_grad.add_stop_color(offset=1,    color='#b71c1c')  # dark red
    dwg.defs.add(flame_grad)

    # Decorative left dot
    dwg.add(dwg.circle(center=(30, 40), r=6, fill='#58a6ff', opacity=0.8))
    dwg.add(dwg.circle(center=(30, 40), r=3, fill='white', opacity=0.4))

    # Title
    dwg.add(dwg.text('Contribution Streak', insert=(260, 45),
                     fill='#c9d1d9', font_family='system-ui,sans-serif',
                     font_size=28, font_weight='bold', text_anchor='middle'))

    # Flame icon
    flame_path_data = (
        "M12 2 Q8 0 4 6 Q2 10 6 16 Q8 20 12 22 "
        "Q16 20 18 16 Q22 10 20 6 Q16 0 12 2 Z "
        "M12 4 Q10 8 12 12 Q14 8 12 4 Z"
    )
    flame = dwg.g(transform='translate(40, 55) scale(2.0)', fill='url(#flameGrad)')
    flame.add(dwg.path(d=flame_path_data))
    flame['filter'] = 'url(#glow)'
    dwg.add(flame)

    # Stats
    stats = [
        (current,  "Current Streak",   130),
        (longest,  "Longest Streak",   260),
        (total,    "Total This Year",  390)
    ]

    for value, label, x in stats:
        dwg.add(dwg.text(str(value), insert=(x, 125),
                         fill='white', font_family='monospace', font_size=40,
                         font_weight='bold', text_anchor='middle', letter_spacing='-1'))
        dwg.add(dwg.text(label.upper(), insert=(x, 155),
                         fill='#8b949e', font_family='system-ui,sans-serif',
                         font_size=13, text_anchor='middle', letter_spacing='1'))

    # Footer
    dwg.add(dwg.text(f'@{username}', insert=(260, 195),
                     fill='#8b949e', font_family='system-ui,sans-serif',
                     font_size=14, text_anchor='middle'))

    os.makedirs('assets', exist_ok=True)
    dwg.save()
    print("SVG saved to assets/streak.svg")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise ValueError("Username (repository owner) must be provided as first argument")

    username = sys.argv[1].strip()
    print(f"Generating streak stats for GitHub user: {username}")

    daily_counts, total_contribs = fetch_contributions(username)
    print(f"Total contributions (last 365 days): {total_contribs}")
    print(f"Days with contributions: {len(daily_counts)}")

    current, longest = calculate_streaks(daily_counts)
    print(f"Current streak: {current}")
    print(f"Longest streak: {longest}")

    generate_svg(current, longest, total_contribs, username)
    print("Done!")
