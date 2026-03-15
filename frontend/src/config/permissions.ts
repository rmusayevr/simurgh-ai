import type { ProjectRole } from '../types';

// Re-export so existing imports from this file keep working
export type { ProjectRole };

export type Permission =
    | 'DELETE_PROJECT'
    | 'MANAGE_MEMBERS'
    | 'APPROVE_PROPOSAL'
    | 'CONVENE_COUNCIL'
    | 'EDIT_CONTENT'
    | 'VIEW_ONLY';

export const ROLE_PERMISSIONS: Readonly<Record<ProjectRole, ReadonlyArray<Permission>>> = {
    OWNER: ['DELETE_PROJECT', 'MANAGE_MEMBERS', 'APPROVE_PROPOSAL', 'CONVENE_COUNCIL', 'EDIT_CONTENT', 'VIEW_ONLY'],
    ADMIN: ['MANAGE_MEMBERS', 'APPROVE_PROPOSAL', 'CONVENE_COUNCIL', 'EDIT_CONTENT', 'VIEW_ONLY'],
    EDITOR: ['CONVENE_COUNCIL', 'EDIT_CONTENT', 'VIEW_ONLY'],
    VIEWER: ['VIEW_ONLY'],
} as const;

export const hasPermission = (
    role: ProjectRole | null | undefined,
    action: Permission
): boolean => {
    if (!role) return false;
    return ROLE_PERMISSIONS[role].includes(action);
};

export const getPermissions = (
    role: ProjectRole | null | undefined
): ReadonlyArray<Permission> => {
    if (!role) return [];
    return ROLE_PERMISSIONS[role];
};
