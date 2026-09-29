import { getUserRole } from "./api/users";

export async function fetchRole() {
  const response = await getUserRole();
  if (response.is_manager) {
    return "manager";
  } else if (response.is_admin) {
    return "admin";
  } else {
    return "user";
  }
}
