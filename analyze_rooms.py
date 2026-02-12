"""
Room Data Analyzer
Analyzes the scraped room timetable data and generates insights
"""

import json
import pandas as pd
from datetime import datetime
from collections import defaultdict


class RoomDataAnalyzer:
    def __init__(self, data_file='rooms_complete_data.json'):
        self.data_file = data_file
        self.data = None
        self.load_data()
    
    def load_data(self):
        """Load the scraped JSON data"""
        try:
            with open(self.data_file, 'r') as f:
                self.data = json.load(f)
            print(f"✅ Loaded data for {self.data['total_rooms']} rooms")
        except FileNotFoundError:
            print(f"❌ File not found: {self.data_file}")
            print("   Please run the scraper first!")
            exit(1)
    
    def find_available_rooms(self, day=None, time_slot=None, min_availability=50):
        """
        Find rooms that are available based on criteria
        
        Args:
            day: Specific day (Mon, Tue, etc.) or None for any day
            time_slot: Specific time slot or None for any time
            min_availability: Minimum availability percentage (default 50%)
        """
        available = []
        
        for room in self.data['rooms']:
            room_num = room['room']
            schedule = room['schedule']
            
            # Calculate overall availability
            total_slots = 0
            free_slots = 0
            
            for d, slots in schedule.items():
                if day and d != day:
                    continue
                
                for slot in slots:
                    if time_slot and time_slot not in slot['time_slot']:
                        continue
                    
                    total_slots += 1
                    if not slot['is_occupied']:
                        free_slots += 1
            
            if total_slots > 0:
                availability = (free_slots / total_slots) * 100
                
                if availability >= min_availability:
                    available.append({
                        'room': room_num,
                        'availability': round(availability, 2),
                        'free_slots': free_slots,
                        'total_slots': total_slots
                    })
        
        # Sort by availability
        available.sort(key=lambda x: x['availability'], reverse=True)
        return available
    
    def find_free_at_time(self, day, time_slot_contains):
        """
        Find all rooms free at a specific day and time
        
        Args:
            day: Day name (Mon, Tue, Wed, Thu, Fri, Sat, Sun)
            time_slot_contains: Part of time slot to match (e.g., "09:00")
        """
        free_rooms = []
        
        for room in self.data['rooms']:
            room_num = room['room']
            schedule = room['schedule'].get(day, [])
            
            for slot in schedule:
                if time_slot_contains in slot['time_slot']:
                    if not slot['is_occupied']:
                        free_rooms.append({
                            'room': room_num,
                            'time_slot': slot['time_slot']
                        })
        
        return free_rooms
    
    def get_room_schedule(self, room_number):
        """Get full schedule for a specific room"""
        for room in self.data['rooms']:
            if str(room['room']) == str(room_number):
                return room['schedule']
        return None
    
    def analyze_peak_hours(self):
        """Identify peak usage hours across all rooms"""
        time_usage = defaultdict(lambda: {'total': 0, 'occupied': 0})
        
        for room in self.data['rooms']:
            for day, slots in room['schedule'].items():
                for slot in slots:
                    time = slot['time_slot']
                    time_usage[time]['total'] += 1
                    if slot['is_occupied']:
                        time_usage[time]['occupied'] += 1
        
        # Calculate percentages
        peak_times = []
        for time, counts in time_usage.items():
            if counts['total'] > 0:
                usage_pct = (counts['occupied'] / counts['total']) * 100
                peak_times.append({
                    'time_slot': time,
                    'usage_percentage': round(usage_pct, 2),
                    'rooms_occupied': counts['occupied'],
                    'total_rooms': counts['total']
                })
        
        peak_times.sort(key=lambda x: x['usage_percentage'], reverse=True)
        return peak_times
    
    def analyze_by_day(self):
        """Analyze usage by day of week"""
        day_usage = defaultdict(lambda: {'total': 0, 'occupied': 0})
        
        for room in self.data['rooms']:
            for day, slots in room['schedule'].items():
                for slot in slots:
                    day_usage[day]['total'] += 1
                    if slot['is_occupied']:
                        day_usage[day]['occupied'] += 1
        
        day_stats = []
        for day, counts in day_usage.items():
            if counts['total'] > 0:
                usage_pct = (counts['occupied'] / counts['total']) * 100
                day_stats.append({
                    'day': day,
                    'usage_percentage': round(usage_pct, 2),
                    'slots_occupied': counts['occupied'],
                    'total_slots': counts['total']
                })
        
        return day_stats
    
    def export_to_csv(self, output_file='room_analysis.csv'):
        """Export all room data to CSV"""
        rows = []
        
        for room in self.data['rooms']:
            room_num = room['room']
            for day, slots in room['schedule'].items():
                for slot in slots:
                    rows.append({
                        'Room': room_num,
                        'Day': day,
                        'Time Slot': slot['time_slot'],
                        'Occupied': slot['is_occupied'],
                        'Content': slot['content']
                    })
        
        df = pd.DataFrame(rows)
        df.to_csv(f'/mnt/user-data/outputs/{output_file}', index=False)
        print(f"✅ Exported to {output_file}")
    
    def export_availability_report(self, output_file='availability_report.csv'):
        """Export room availability summary"""
        rows = []
        
        for room in self.data['rooms']:
            room_num = room['room']
            total_slots = 0
            occupied_slots = 0
            
            for day, slots in room['schedule'].items():
                for slot in slots:
                    total_slots += 1
                    if slot['is_occupied']:
                        occupied_slots += 1
            
            if total_slots > 0:
                availability = ((total_slots - occupied_slots) / total_slots) * 100
                rows.append({
                    'Room': room_num,
                    'Total Slots': total_slots,
                    'Occupied Slots': occupied_slots,
                    'Free Slots': total_slots - occupied_slots,
                    'Availability %': round(availability, 2)
                })
        
        df = pd.DataFrame(rows)
        df = df.sort_values('Availability %', ascending=False)
        df.to_csv(f'/mnt/user-data/outputs/{output_file}', index=False)
        print(f"✅ Exported to {output_file}")
    
    def print_summary(self):
        """Print a comprehensive summary"""
        print("\n" + "="*70)
        print("📊 ROOM TIMETABLE ANALYSIS")
        print("="*70)
        
        print(f"\n📈 Overall Statistics:")
        print(f"   Total rooms analyzed: {self.data['total_rooms']}")
        print(f"   Data timestamp: {self.data['timestamp']}")
        
        # Most available rooms
        print(f"\n🟢 Most Available Rooms (Top 10):")
        most_available = self.find_available_rooms(min_availability=0)[:10]
        for room in most_available:
            print(f"   Room {room['room']}: {room['availability']}% available "
                  f"({room['free_slots']}/{room['total_slots']} slots free)")
        
        # Least available rooms
        print(f"\n🔴 Least Available Rooms (Top 10):")
        least_available = sorted(
            self.find_available_rooms(min_availability=0),
            key=lambda x: x['availability']
        )[:10]
        for room in least_available:
            print(f"   Room {room['room']}: {room['availability']}% available "
                  f"({room['free_slots']}/{room['total_slots']} slots free)")
        
        # Peak hours
        print(f"\n⏰ Peak Usage Hours (Top 5):")
        peak_hours = self.analyze_peak_hours()[:5]
        for peak in peak_hours:
            print(f"   {peak['time_slot']}: {peak['usage_percentage']}% occupied "
                  f"({peak['rooms_occupied']}/{peak['total_rooms']} rooms)")
        
        # Day analysis
        print(f"\n📅 Usage by Day:")
        day_stats = self.analyze_by_day()
        for stat in day_stats:
            print(f"   {stat['day']}: {stat['usage_percentage']}% occupied "
                  f"({stat['slots_occupied']}/{stat['total_slots']} slots)")
        
        print("\n" + "="*70 + "\n")


def main():
    """Example usage"""
    # Initialize analyzer
    analyzer = RoomDataAnalyzer('rooms_complete_data.json')
    
    # Print comprehensive summary
    analyzer.print_summary()
    
    # Export data
    analyzer.export_to_csv()
    analyzer.export_availability_report()
    
    # Example queries
    print("\n📍 Example Queries:")
    
    # Find rooms free Monday morning
    print("\n1. Rooms free Monday at 9 AM:")
    free_rooms = analyzer.find_free_at_time('Mon', '09:00')
    for room in free_rooms[:10]:
        print(f"   Room {room['room']} at {room['time_slot']}")
    
    # Find rooms with >80% availability
    print("\n2. Rooms with >80% availability:")
    highly_available = analyzer.find_available_rooms(min_availability=80)
    for room in highly_available[:10]:
        print(f"   Room {room['room']}: {room['availability']}%")
    
    # Get specific room schedule
    print("\n3. Schedule for Room 5306:")
    schedule = analyzer.get_room_schedule(5306)
    if schedule:
        for day, slots in schedule.items():
            occupied = sum(1 for s in slots if s['is_occupied'])
            print(f"   {day}: {occupied}/{len(slots)} slots occupied")
    
    print("\n✅ Analysis complete!\n")


if __name__ == "__main__":
    main()
