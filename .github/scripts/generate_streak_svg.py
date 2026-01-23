import requests
import svgwrite
import os
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta  # pip install python-dateutil (but it's often pre-installed; if not, add to workflow)

def fetch_contributions(username):
    """Fetch contribution calendar data for the last year."""
    end_date = datetime.now().date()
    start_date = end_date - relativedelta(years=1)
    
    url = f"https://api.github.com/users/{username}/events/public"
    headers = {'User-Agent': 'Streak-Stats-Generator'}
    
    # Fetch events (we'll count daily contributions from here)
    all_events = []
    page = 1
    while True:
        params = {'per_page': 100, 'page': page}
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            raise Exception(f"API error: {response.status_code}")
        events = response.json()
        if not events:
            break
        all_events.extend(events)
        page += 1
    
    # Aggregate daily counts (simple: count unique days with events)
    daily_counts = {}
    for event in all_events:
        if 'created_at' in event:
            date_str = event['created_at'][:10]  # YYYY-MM-DD
            daily_counts[date_str] = daily_counts.get(date_str, 0) + 1
    
    # Filter to last year
    filtered_counts = {date: count for date, count in daily_counts.items()
                       if start_date <= datetime.strptime(date, '%Y-%m-%d').date() <= end_date}
    
    return filtered_counts

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
    """Generate the SVG using svgwrite, mimicking the original design."""
    dwg = svgwrite.Drawing('assets/streak.svg', size=('400px', '160px'), profile='tiny')
    
    # Background (dark gradient)
    dwg.add(dwg.rect(insert=(0, 0), size=('100%', '100%'), rx=12, ry=12,
                     fill='url(#bgGrad)'))
    dwg.defs.add(dwg.linearGradient(id='bgGrad', gradientUnits='userSpaceOnUse',
                                    x1=0, y1=0, x2=0, y2='100%',
                                    stops=[
                                        ('0%', '#161b22'),
                                        ('100%', '#0d1117')
                                    ]))
    
    # Title
    dwg.add(dwg.text('GitHub Streak', insert=(200, 25), fill='#7dd3fc', font_family='sans-serif',
                     font_size=20, font_weight='bold', text_anchor='middle'))
    
    # Flame icon (simple SVG path mimicking the original)
    flame_path = 'M12 2C13.1 2 14 2.9 14 4c0 1-1.1 2.1-2 3-1 .9-2 0-2 0-1-.9-2-2.1-2-3 0-1.1.9-2 2-2zm0 24c-1.1 0-2-.9-2-2 0-1.1.9-2 2-2s2 .9 2 2c0 1.1-.9 2-2 2zM12 12c-2.2 0-4 1.8-4 4s1.8 4 4 4 4-1.8 4-4-1.8-4-4-4z'  # Approximate flame
    dwg.add(dwg.g(transform='scale(0.05) translate(100, 50)', fill='#f59e0b'))
    dwg.add(dwg.path(d=flame_path, transform='scale(20) translate(5, 2)'))  # Scaled flame
    
    # Stats text
    y_offset = 70
    stats = [
        (f'{current_streak}', 'Current Streak'),
        (f'{longest_streak}', 'Longest Streak'),
        (f'{total_contribs}', 'Total Contribs')
    ]
    for i, (value, label) in enumerate(stats):
        x = 50 + i * 120
        dwg.add(dwg.text(value, insert=(x, y_offset), fill='#ffffff', font_family='monospace',
                         font_size=24, font_weight='bold', text_anchor='middle'))
        dwg.add(dwg.text(label, insert=(x, y_offset + 25), fill='#8b949e', font_family='sans-serif',
                         font_size=10, text_anchor='middle'))
    
    # Username footer
    dwg.add(dwg.text(f'@{username}', insert=(200, 145), fill='#8b949e', font_family='sans-serif',
                     font_size=12, text_anchor='middle'))
    
    # Optional: Add a simple calendar bar (last 7 days, for visual)
    bar_y = 100
    recent_dates = sorted(daily_counts.keys())[-7:] if 'daily_counts' in globals() else []
    for i, date_str in enumerate(recent_dates[-7:]):
        contrib = daily_counts.get(date_str, 0)
        height = min(20, contrib * 2)  # Scale height based on contribs
        color = '#0e4429' if contrib > 0 else '#161b22'
        dwg.add(dwg.rect(insert=(40 + i * 25, bar_y - height), size=(20, height),
                         rx=3, fill=color))
    
    dwg.save()

if __name__ == '__main__':
    username = os.getenv('GITHUB_USERNAME')
    if not username:
        raise ValueError("Set GITHUB_USERNAME env var")
    
    daily_counts = fetch_contributions(username)
    current, longest, total = calculate_streaks(daily_counts)
    generate_svg(current, longest, total, username)
    print(f"Generated SVG: Current={current}, Longest={longest}, Total={total}")
