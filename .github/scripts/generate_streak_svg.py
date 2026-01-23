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
    total = calendar['totalContributions']

    daily_counts = {}
    for week in calendar['weeks']:
        for day in week['contributionDays']:
            count = day['contributionCount']
            if count > 0:
                daily_counts[day['date'][:10]] = count

    return daily_counts, total


def calculate_streaks(daily_counts):
    if not daily_counts:
        return 0, 0, datetime.now().strftime("%b %d, %Y")

    dates = sorted(daily_counts.keys())

    current = 0
    for date_str in reversed(dates):
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        delta = (datetime.now().date() - date).days
        if delta <= current:
            current += 1
        else:
            break

    longest = 0
    streak = 0
    prev = None
    longest_start = ""
    longest_end = ""
    for date_str in dates:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        if prev is None or (date - prev).days == 1:
            streak += 1
            if streak > longest:
                longest = streak
                longest_start = prev.strftime("%b %d, %Y") if prev else date.strftime("%b %d, %Y")
                longest_end = date.strftime("%b %d, %Y")
        else:
            streak = 1
        prev = date

    return current, longest, f"{longest_start} - {longest_end}" if longest_start else "N/A"


def get_theme_colors(theme_slug):
    themes = {
        'ocean-blue-dark': {
            'background': '#1A1B27',
            'border': '#E4E2E2',
            'accent': '#5B9EFF',
            'current': '#A78BFA',
            'label': '#5B9EFF',
            'range': '#34D399',
            'flame': '#5B9EFF'
        },
        'ocean-blue-light': {
            'background': '#F8FAFC',
            'border': '#CBD5E1',
            'accent': '#3B82F6',
            'current': '#8B5CF6',
            'label': '#1D4ED8',
            'range': '#10B981',
            'flame': '#3B82F6'
        },
        'emerald-forest-dark': {
            'background': '#1A1B27',
            'border': '#E4E2E2',
            'accent': '#10B981',
            'current': '#34D399',
            'label': '#10B981',
            'range': '#FBBF24',
            'flame': '#10B981'
        },
        'mint-breeze-light': {
            'background': '#F8FAFC',
            'border': '#CBD5E1',
            'accent': '#10B981',
            'current': '#34D399',
            'label': '#065F46',
            'range': '#F59E0B',
            'flame': '#059669'
        }
    }
    return themes.get(theme_slug, themes['ocean-blue-dark'])


def generate_svg(current, longest, total, username, longest_range, theme_slug):
    colors = get_theme_colors(theme_slug)

    dwg = svgwrite.Drawing('assets/streak.svg', size=('495px', '195px'), viewBox='0 0 495 195', debug=False)

    dwg.defs.add(dwg.style("""
        @keyframes currstreak {
            0% { font-size: 3px; opacity: 0.2; }
            80% { font-size: 34px; opacity: 1; }
            100% { font-size: 28px; opacity: 1; }
        }
        @keyframes fadein {
            0% { opacity: 0; }
            100% { opacity: 1; }
        }
    """))

    clip = dwg.clipPath(id='outer_rectangle')
    clip.add(dwg.rect(insert=(0, 0), size=(495, 195), rx=4.5))
    dwg.defs.add(clip)

    mask = dwg.mask(id='mask_out_ring_behind_fire')
    mask.add(dwg.rect(insert=(0, 0), size=(495, 195), fill='white'))
    mask.add(dwg.ellipse(center=(247.5, 32), r=(13, 18), fill='black'))
    dwg.defs.add(mask)

    main = dwg.g(clip_path='url(#outer_rectangle)')
    dwg.add(main)

    main.add(dwg.rect(insert=(0.5, 0.5), size=(494, 194), rx=4.5, fill=colors['background'], stroke=colors['border']))

    main.add(dwg.line(start=(165, 28), end=(165, 170), stroke=colors['border'], stroke_width=1))
    main.add(dwg.line(start=(330, 28), end=(330, 170), stroke=colors['border'], stroke_width=1))

    # Total Contributions
    total_g = dwg.g(transform='translate(82.5, 48)')
    total_g.add(dwg.text(str(total), insert=(0, 32), fill=colors['accent'],
                         font_family='"Segoe UI", Ubuntu, sans-serif',
                         font_size=28, font_weight=700, text_anchor='middle',
                         style='opacity: 0; animation: fadein 0.5s linear forwards 0.6s'))
    main.add(total_g)

    label_g = dwg.g(transform='translate(82.5, 84)')
    label_g.add(dwg.text('Total Contributions', insert=(0, 32), fill=colors['label'],
                         font_family='"Segoe UI", Ubuntu, sans-serif',
                         font_size=14, text_anchor='middle',
                         style='opacity: 0; animation: fadein 0.5s linear forwards 0.7s'))
    main.add(label_g)

    range_g = dwg.g(transform='translate(82.5, 114)')
    range_g.add(dwg.text('May 9, 2019 - Present', insert=(0, 32), fill=colors['range'],
                         font_family='"Segoe UI", Ubuntu, sans-serif',
                         font_size=12, text_anchor='middle',
                         style='opacity: 0; animation: fadein 0.5s linear forwards 0.8s'))
    main.add(range_g)

    # Current Streak
    center_g = dwg.g(transform='translate(247.5, 108)')
    center_g.add(dwg.text('Current Streak', insert=(0, 32), fill=colors['current'],
                          font_family='"Segoe UI", Ubuntu, sans-serif',
                          font_size=14, font_weight=700, text_anchor='middle',
                          style='opacity: 0; animation: fadein 0.5s linear forwards 0.9s'))
    main.add(center_g)

    range_center = dwg.g(transform='translate(247.5, 145)')
    range_center.add(dwg.text(datetime.now().strftime("%b %d"), insert=(0, 21), fill=colors['range'],
                              font_family='"Segoe UI", Ubuntu, sans-serif',
                              font_size=12, text_anchor='middle',
                              style='opacity: 0; animation: fadein 0.5s linear forwards 0.9s'))
    main.add(range_center)

    ring_g = dwg.g(mask='url(#mask_out_ring_behind_fire)')
    ring_g.add(dwg.circle(center=(247.5, 71), r=40, fill='none',
                          stroke=colors['accent'], stroke_width=5,
                          style='opacity: 0; animation: fadein 0.5s linear forwards 0.4s'))
    main.add(ring_g)

    flame_g = dwg.g(transform='translate(247.5, 19.5)',
                    style='opacity: 0; animation: fadein 0.5s linear forwards 0.6s')
    flame_g.add(dwg.path(d="M -12 -0.5 L 15 -0.5 L 15 23.5 L -12 23.5 L -12 -0.5 Z", fill='none'))
    flame_g.add(dwg.path(d="M 1.5 0.67 C 1.5 0.67 2.24 3.32 2.24 5.47 C 2.24 7.53 0.89 9.2 -1.17 9.2 C -3.23 9.2 -4.79 7.53 -4.79 5.47 L -4.76 5.11 C -6.78 7.51 -8 10.62 -8 13.99 C -8 18.41 -4.42 22 0 22 C 4.42 22 8 18.41 8 13.99 C 8 8.6 5.41 3.79 1.5 0.67 Z M -0.29 19 C -2.07 19 -3.51 17.6 -3.51 15.86 C -3.51 14.24 -2.46 13.1 -0.7 12.74 C 1.07 12.38 2.9 11.53 3.92 10.16 C 4.31 11.45 4.51 12.81 4.51 14.2 C 4.51 16.85 2.36 19 -0.29 19 Z", fill=colors['flame']))
    main.add(flame_g)

    curr_num_g = dwg.g(transform='translate(247.5, 48)')
    curr_num_g.add(dwg.text(str(current), insert=(0, 32), fill=colors['current'],
                            font_family='"Segoe UI", Ubuntu, sans-serif',
                            font_size=28, font_weight=700, text_anchor='middle',
                            style='animation: currstreak 0.6s linear forwards'))
    main.add(curr_num_g)

    # Longest Streak
    long_g = dwg.g(transform='translate(412.5, 48)')
    long_g.add(dwg.text(str(longest), insert=(0, 32), fill=colors['accent'],
                        font_family='"Segoe UI", Ubuntu, sans-serif',
                        font_size=28, font_weight=700, text_anchor='middle',
                        style='opacity: 0; animation: fadein 0.5s linear forwards 1.2s'))
    main.add(long_g)

    long_label = dwg.g(transform='translate(412.5, 84)')
    long_label.add(dwg.text('Longest Streak', insert=(0, 32), fill=colors['label'],
                            font_family='"Segoe UI", Ubuntu, sans-serif',
                            font_size=14, text_anchor='middle',
                            style='opacity: 0; animation: fadein 0.5s linear forwards 1.3s'))
    main.add(long_label)

    long_range_g = dwg.g(transform='translate(412.5, 114)')
    long_range_g.add(dwg.text(longest_range, insert=(0, 32), fill=colors['range'],
                              font_family='"Segoe UI", Ubuntu, sans-serif',
                              font_size=12, text_anchor='middle',
                              style='opacity: 0; animation: fadein 0.5s linear forwards 1.4s'))
    main.add(long_range_g)

    # Save directly to final location
    os.makedirs('assets/Streaks', exist_ok=True)
    final_path = f'assets/Streaks/streak-{theme_slug}.svg'
    dwg.filename = final_path
    dwg.save()
    print(f"Saved: {final_path}")


if __name__ == '__main__':
    theme_slug = 'ocean-blue-dark'
    if len(sys.argv) >= 3:
        theme_slug = sys.argv[2].strip().lower()

    if len(sys.argv) < 2:
        raise ValueError("Provide username as first argument")

    username = sys.argv[1].strip()
    print(f"User: {username} | Theme: {theme_slug}")

    daily_counts, total = fetch_contributions(username)
    print(f"Total: {total} | Active days: {len(daily_counts)}")

    current, longest, longest_range = calculate_streaks(daily_counts)
    print(f"Current: {current} | Longest: {longest} | Range: {longest_range}")

    generate_svg(current, longest, total, username, longest_range, theme_slug)
    print("Done!")
