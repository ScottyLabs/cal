import { apiGet } from "./api";
import { CategoryOrg } from "../types";

// The API identifies the caller from the bearer token alone, so none of these
// take a user id.

export const getAdminCategories = () => {
    return apiGet<CategoryOrg[]>("/users/get_admin_categories");
};

export const getUserID = () => {
    return apiGet<{ user_id: number }>("/users/get_user_id");
};

export interface RoleResponse {
    is_manager: boolean;
    is_admin: boolean;
    is_site_admin: boolean;
    roles: { role: string; org_id: number }[];
}

export const getUserRole = (): Promise<RoleResponse> => {
    return apiGet<RoleResponse>("/users/get_role");
}
