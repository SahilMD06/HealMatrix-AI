/**
 * Client-side mirrors of the backend vocabulary.
 * Kept in one file so labels, routes and role gates never drift across components.
 */

export const ROLES = {
  ADMIN: 'admin',
  DOCTOR: 'doctor',
  NURSE: 'nurse',
  PHARMACIST: 'pharmacist',
  MANAGER: 'manager',
  SUSTAINABILITY_OFFICER: 'sustainability_officer',
}

export const ROLE_LABELS = {
  [ROLES.ADMIN]: 'Administrator',
  [ROLES.DOCTOR]: 'Doctor',
  [ROLES.NURSE]: 'Nurse',
  [ROLES.PHARMACIST]: 'Pharmacist',
  [ROLES.MANAGER]: 'Hospital Manager',
  [ROLES.SUSTAINABILITY_OFFICER]: 'Sustainability Officer',
}

export const ROUTES = {
  LANDING: '/',
  LOGIN: '/login',
  REGISTER: '/register',
  ADMIN: '/dashboard/admin',
  DOCTOR: '/dashboard/doctor',
  EMERGENCY: '/dashboard/emergency',
  INVENTORY: '/dashboard/inventory',
  SUSTAINABILITY: '/dashboard/sustainability',
  EXECUTIVE: '/dashboard/executive',
  DIGITAL_TWIN: '/digital-twin',
  ANALYTICS: '/analytics',
  AGENTS: '/agents',
  REPORTS: '/reports',
  NOTIFICATIONS: '/notifications',
  ASSISTANT: '/assistant',
  SETTINGS: '/settings',
}

export const ROLE_HOME = {
  [ROLES.ADMIN]: ROUTES.ADMIN,
  [ROLES.DOCTOR]: ROUTES.DOCTOR,
  [ROLES.NURSE]: ROUTES.EMERGENCY,
  [ROLES.PHARMACIST]: ROUTES.INVENTORY,
  [ROLES.MANAGER]: ROUTES.EXECUTIVE,
  [ROLES.SUSTAINABILITY_OFFICER]: ROUTES.SUSTAINABILITY,
}

export const AGENTS = [
  { key: 'patient_triage', name: 'Patient Triage', domain: 'clinical' },
  { key: 'disease_forecast', name: 'Disease Forecast', domain: 'clinical' },
  { key: 'bed_allocation', name: 'Bed Allocation', domain: 'operations' },
  { key: 'medicine_intelligence', name: 'Medicine Intelligence', domain: 'operations' },
  { key: 'energy_optimization', name: 'Energy Optimization', domain: 'sustainability' },
  { key: 'water_conservation', name: 'Water Conservation', domain: 'sustainability' },
  { key: 'biomedical_waste', name: 'Biomedical Waste', domain: 'sustainability' },
  { key: 'carbon_intelligence', name: 'Carbon Intelligence', domain: 'sustainability' },
  { key: 'ambulance_dispatch', name: 'Ambulance Dispatch', domain: 'emergency' },
  { key: 'executive_decision', name: 'Executive Decision', domain: 'strategy' },
]

export const NOTIFICATION_TYPES = {
  MEDICINE_EXPIRY: 'medicine_expiry',
  EMERGENCY_ALERT: 'emergency_alert',
  WASTE_PICKUP: 'waste_pickup',
  BED_AVAILABILITY: 'bed_availability',
  WATER_LEAK: 'water_leak',
  HIGH_ENERGY: 'high_energy',
  OUTBREAK_WARNING: 'outbreak_warning',
}

export const SDG_GOALS = [
  { number: 3, title: 'Good Health and Well-Being', primary: true },
  { number: 7, title: 'Affordable and Clean Energy', primary: false },
  { number: 9, title: 'Industry, Innovation and Infrastructure', primary: false },
  { number: 11, title: 'Sustainable Cities and Communities', primary: false },
  { number: 12, title: 'Responsible Consumption and Production', primary: false },
  { number: 13, title: 'Climate Action', primary: false },
]

export const STORAGE_KEYS = {
  ACCESS_TOKEN: 'healmatrix.access_token',
  REFRESH_TOKEN: 'healmatrix.refresh_token',
  THEME: 'healmatrix.theme',
  HOSPITAL: 'healmatrix.hospital_id',
}
