import requests
import json
import sys
import os
from datetime import datetime, timedelta
import svgwrite

def fetch_contributions(username):
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
        raise ValueError("GITHUB_TOKEN missing or invalid!")

    print(f"DEBUG: Token prefix = {token[:4]}... (length: {len(token)})")

    headers = {
        'Authorization': f'Bearer {token}',
        'User-Agent': 'Streak-Generator'
    }

    url = "https://api.github.com/graphql"
    response = requests.post(url, json={'query': query, 'variables': variables}, headers=headers)

    if response.status_code != 200:
        raise Exception(f"HTTP {response.status_code}: {response.text}")

    data = response.json()
    if 'errors' in data:
        raise Exception(f"GraphQL errors: {json.dumps(data['errors'], indent=2)}")

    user_data = data.get('data', {}).get('user')
    if not user_data:
        raise Exception(f"User '{username}' not found")

    calendar = user_data['contributionsCollection']['contributionCalendar']
    total_contribs = calendar['totalContributions']

    daily_counts = {}
    for week in calendar['weeks']:
        for day in week['contributionDays']:
            count = day['contributionCount']
            if count > 0:
                daily_counts[day['date'][:10]] = count

    return daily_counts, total_contribs


def calculate_streaks(daily_counts):
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

    # Flame gradient (orange to yellow glow)
    flame_grad = dwg.linearGradient(start=(0, 0), end=(0, '100%'), id='flameGrad')
    flame_grad.add_stop_color(offset=0, color='#ff9800')
    flame_grad.add_stop_color(offset=0.5, color='#ff5722')
    flame_grad.add_stop_color(offset=1, color='#ffeb3b')
    dwg.defs.add(flame_grad)

    # Decorative dot on left side (as requested)
    dwg.add(dwg.circle(center=(30, 40), r=6, fill='#58a6ff', opacity=0.8))
    dwg.add(dwg.circle(center=(30, 40), r=3, fill='white', opacity=0.4))  # inner glow

    # Title
    dwg.add(dwg.text('Contribution Streak', insert=(260, 45),
                     fill='#c9d1d9', font_family='system-ui,sans-serif',
                     font_size=28, font_weight='bold', text_anchor='middle'))

    # Improved flame icon (more detailed path from streak stats style)
    flame = dwg.g(transform='translate(40, 60) scale(2.2)', fill='url(#flameGrad)')
    flame.add(dwg.path(d=(
        "M 8 0 C 9 0 10 1 10 2 C 10 3 9 4 8 5 C 7 6 6 5 6 5 "
        "C 5 4 4 3 4 2 C 4 1 5 0 6 0 Z "
        "M 8 18 C 7 18 6 17 6 16 C 6 15 7 14 8 14 C 9 14 10 15 10 16 C 10 17 9 18 8 18 Z "
        "M 8 8 C 6 8 4 10 4 12 C 4 14 6 16 8 16 C 10 16 12 14 12 12 C 12 10 10 8 8 8 Z "
        "M 12 4 C 13 4 14 5 14 6 C 14 8 12 10 10 11 C 9 11 8 10 8 9 C 8 7 10 5 12 4 Z"
    )))
    # Add subtle outer glow (optional filter)
    glow = dwg.filter(id='glow', x='-50%', y='-50%', width='200%', height='200%')
    glow.feGaussianBlur(stdDeviation=2.5, result='blur')
    glow.feMerge().feMergeNode().feFlood(flood_color='#ff9800', flood_opacity=0.4)
    glow.feMerge().feMergeNode().feMergeNode(in='blur')
    dwg.defs.add(glow)
    flame['filter'] = 'url(#glow)'
    dwg.add(flame)

    # Stats (centered layout with icons-like feel)
    stats = [
        (current, "Current Streak", 130),
        (longest, "Longest Streak", 260),
        (total, "Total This Year", 390)
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
        raise ValueError("Provide username as argument")
    username = sys.argv[1].strip()
    print(f"Generating for: {username}")

    daily_counts, total = fetch_contributions(username)
    print(f"Total contribs: {total} | Active days: {len(daily_counts)}")

    current, longest = calculate_streaks(daily_counts)
    print(f"Current: {current} | Longest: {longest}")

    generate_svg(current, longest, total, username)
    print("Done!")
