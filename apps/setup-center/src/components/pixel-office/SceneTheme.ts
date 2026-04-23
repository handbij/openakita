export interface FurnitureStyle {
  label: string;
  tint: number;
}

export interface SceneTheme {
  id: string;
  name: string;
  description: string;

  palette: {
    background: string;
    floor: [string, string];
    wall: [string, string];
    accent: string;
  };

  furniture: {
    workstation: FurnitureStyle;
    chair: FurnitureStyle;
    meetingTable: FurnitureStyle;
    restArea: FurnitureStyle;
    debugStation: FurnitureStyle;
    entrance: FurnitureStyle;
  };

  roomLabels: {
    department: string;
    meetingRoom: string;
    breakRoom: string;
    debugArea: string;
    entrance: string;
  };

  characterStyle: {
    outfitBase: string;
    accessoryMap: Record<string, string>;
  };

  ambiance: {
    particles?: 'none' | 'dust' | 'snow' | 'leaves' | 'stars' | 'sparks' | 'bubbles';
    musicHint?: string;
  };
}

function hex(c: string): number {
  return parseInt(c.replace('#', ''), 16);
}

export const THEME_PRESETS: Record<string, SceneTheme> = {
  office: {
    id: 'office',
    name: 'Modern Office',
    description: 'Standard corporate office environment',
    palette: {
      background: '#2C2C3A',
      floor: ['#C4A882', '#B89B72'],
      wall: ['#8899AA', '#6B7A8A'],
      accent: '#4A90D9',
    },
    furniture: {
      workstation: { label: 'Desk', tint: hex('#8B7355') },
      chair: { label: 'Office Chair', tint: hex('#555555') },
      meetingTable: { label: 'Meeting Table', tint: hex('#6B5B4B') },
      restArea: { label: 'Sofa', tint: hex('#7B6BA5') },
      debugStation: { label: 'Server', tint: hex('#3A4A5A') },
      entrance: { label: 'Main Door', tint: hex('#6B5B4B') },
    },
    roomLabels: { department: 'Department', meetingRoom: 'Meeting Room', breakRoom: 'Lounge', debugArea: 'Server Room', entrance: 'Entrance' },
    characterStyle: { outfitBase: 'suit', accessoryMap: {} },
    ambiance: { particles: 'dust' },
  },

  tech_lab: {
    id: 'tech_lab',
    name: 'Tech Lab',
    description: 'High-tech research and development laboratory',
    palette: {
      background: '#1A1A2E',
      floor: ['#3A3A5A', '#2A2A4A'],
      wall: ['#4A4A6A', '#3A3A5A'],
      accent: '#00D4FF',
    },
    furniture: {
      workstation: { label: 'Lab Bench', tint: hex('#4A5A6A') },
      chair: { label: 'Lab Chair', tint: hex('#3A4A5A') },
      meetingTable: { label: 'Whiteboard Table', tint: hex('#5A6A7A') },
      restArea: { label: 'Rest Pod', tint: hex('#2A3A4A') },
      debugStation: { label: 'Server Array', tint: hex('#1A2A3A') },
      entrance: { label: 'Security Door', tint: hex('#4A5A6A') },
    },
    roomLabels: { department: 'Laboratory', meetingRoom: 'Conference Room', breakRoom: 'Rest Pod', debugArea: 'Data Center', entrance: 'Security Entrance' },
    characterStyle: { outfitBase: 'labcoat', accessoryMap: {} },
    ambiance: { particles: 'sparks' },
  },

  school: {
    id: 'school',
    name: 'School',
    description: 'Educational institution environment',
    palette: {
      background: '#F5F0E8',
      floor: ['#D4C4A8', '#C4B498'],
      wall: ['#E8DCC8', '#D8CCB8'],
      accent: '#FF8C42',
    },
    furniture: {
      workstation: { label: 'School Desk', tint: hex('#A0855C') },
      chair: { label: 'Chair', tint: hex('#8B7355') },
      meetingTable: { label: 'Podium', tint: hex('#6B5B4B') },
      restArea: { label: 'Reading Corner', tint: hex('#8B6914') },
      debugStation: { label: 'Computer Lab', tint: hex('#555555') },
      entrance: { label: 'School Gate', tint: hex('#6B5B4B') },
    },
    roomLabels: { department: 'Classroom', meetingRoom: 'Lecture Hall', breakRoom: 'Cafeteria', debugArea: 'Computer Lab', entrance: 'School Gate' },
    characterStyle: { outfitBase: 'casual', accessoryMap: {} },
    ambiance: { particles: 'none' },
  },

  spaceship: {
    id: 'spaceship',
    name: 'Space Station',
    description: 'Interstellar starship command center',
    palette: {
      background: '#0A0A1A',
      floor: ['#2A2A3A', '#1A1A2A'],
      wall: ['#3A3A4A', '#2A2A3A'],
      accent: '#FF4444',
    },
    furniture: {
      workstation: { label: 'Console', tint: hex('#3A4A5A') },
      chair: { label: 'Seat', tint: hex('#2A3A4A') },
      meetingTable: { label: 'Bridge', tint: hex('#4A5A6A') },
      restArea: { label: 'Living Quarters', tint: hex('#3A4A3A') },
      debugStation: { label: 'Engine Bay', tint: hex('#5A3A2A') },
      entrance: { label: 'Airlock', tint: hex('#5A5A6A') },
    },
    roomLabels: { department: 'Compartment', meetingRoom: 'Command Room', breakRoom: 'Living Quarters', debugArea: 'Engine Bay', entrance: 'Airlock' },
    characterStyle: { outfitBase: 'spacesuit', accessoryMap: {} },
    ambiance: { particles: 'stars' },
  },

  medieval_guild: {
    id: 'medieval_guild',
    name: 'Medieval Guild',
    description: 'Fantasy adventurer guild hall',
    palette: {
      background: '#2A1F14',
      floor: ['#8B7355', '#7A6345'],
      wall: ['#6B5B4B', '#5B4B3B'],
      accent: '#FFD700',
    },
    furniture: {
      workstation: { label: 'Wooden Table', tint: hex('#6B5B4B') },
      chair: { label: 'Wooden Stool', tint: hex('#5B4B3B') },
      meetingTable: { label: 'Round Table', tint: hex('#4B3B2B') },
      restArea: { label: 'Tavern Bench', tint: hex('#7A6345') },
      debugStation: { label: 'Alchemy Table', tint: hex('#5A4A3A') },
      entrance: { label: 'Drawbridge Gate', tint: hex('#4B3B2B') },
    },
    roomLabels: { department: 'Chapter', meetingRoom: 'Council Hall', breakRoom: 'Tavern', debugArea: 'Forge', entrance: 'Drawbridge Gate' },
    characterStyle: { outfitBase: 'armor', accessoryMap: {} },
    ambiance: { particles: 'sparks' },
  },

  game_studio: {
    id: 'game_studio',
    name: 'Game Studio',
    description: 'Creative game development studio',
    palette: {
      background: '#1E1E2E',
      floor: ['#6B5B8D', '#5B4B7D'],
      wall: ['#4A3A6A', '#3A2A5A'],
      accent: '#FF6BFF',
    },
    furniture: {
      workstation: { label: 'Dual-Monitor Workstation', tint: hex('#4A4A6A') },
      chair: { label: 'Gaming Chair', tint: hex('#FF4444') },
      meetingTable: { label: 'Brainstorm Table', tint: hex('#5A5A7A') },
      restArea: { label: 'Arcade Area', tint: hex('#3A3A5A') },
      debugStation: { label: 'Test Lab', tint: hex('#2A2A4A') },
      entrance: { label: 'Entrance', tint: hex('#5A4A6A') },
    },
    roomLabels: { department: 'Team', meetingRoom: 'Brainstorm Room', breakRoom: 'Arcade Area', debugArea: 'Testing Room', entrance: 'Entrance' },
    characterStyle: { outfitBase: 'casual', accessoryMap: {} },
    ambiance: { particles: 'dust' },
  },

  garden: {
    id: 'garden',
    name: 'Garden',
    description: 'Natural outdoor garden workspace',
    palette: {
      background: '#87CEEB',
      floor: ['#5A8A3A', '#4A7A2A'],
      wall: ['#8B7355', '#7A6345'],
      accent: '#FF6B6B',
    },
    furniture: {
      workstation: { label: 'Stone Table', tint: hex('#999999') },
      chair: { label: 'Wooden Chair', tint: hex('#8B7355') },
      meetingTable: { label: 'Gazebo', tint: hex('#6B5B4B') },
      restArea: { label: 'Hammock', tint: hex('#4A7A2A') },
      debugStation: { label: 'Greenhouse', tint: hex('#3A6A2A') },
      entrance: { label: 'Floral Gate', tint: hex('#FF6B6B') },
    },
    roomLabels: { department: 'Garden Area', meetingRoom: 'Gazebo', breakRoom: 'Shade Tree', debugArea: 'Greenhouse', entrance: 'Floral Gate' },
    characterStyle: { outfitBase: 'casual', accessoryMap: {} },
    ambiance: { particles: 'leaves' },
  },

  hospital: {
    id: 'hospital',
    name: 'Medical Facility',
    description: 'Modern hospital environment',
    palette: {
      background: '#E8F0F8',
      floor: ['#D8E8D8', '#C8D8C8'],
      wall: ['#F0F0F0', '#E0E0E0'],
      accent: '#27AE60',
    },
    furniture: {
      workstation: { label: 'Nurse Station', tint: hex('#CCCCCC') },
      chair: { label: 'Wheelchair', tint: hex('#888888') },
      meetingTable: { label: 'Consultation Desk', tint: hex('#AAAAAA') },
      restArea: { label: 'Waiting Area', tint: hex('#99BBAA') },
      debugStation: { label: 'Lab', tint: hex('#88AACC') },
      entrance: { label: 'Emergency Entrance', tint: hex('#CC4444') },
    },
    roomLabels: { department: 'Department', meetingRoom: 'Consultation Room', breakRoom: 'Waiting Area', debugArea: 'Lab', entrance: 'Emergency Entrance' },
    characterStyle: { outfitBase: 'labcoat', accessoryMap: {} },
    ambiance: { particles: 'none' },
  },
};

export function getTheme(id: string): SceneTheme {
  return THEME_PRESETS[id] ?? THEME_PRESETS.office;
}

export function listThemes(): SceneTheme[] {
  return Object.values(THEME_PRESETS);
}
