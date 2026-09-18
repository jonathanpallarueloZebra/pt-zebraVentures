/**
 * Listado curado de iconos Material disponibles para SELECCIONAR (no subir) en
 * el sistema: campos de tipo `icon` (y el icono de entidad del configurador).
 *
 * Cada entrada tiene:
 *  - `icon`: nombre de ligadura de la fuente `material-icons` (lo que se pinta
 *    con `<mat-icon>` y se guarda como valor del campo).
 *  - `label`: nombre EN ESPAÑOL mostrado al usuario en el dropdown.
 *
 * AC-6 del ticket "Crear tipo de campo icono": el campo solo permite elegir
 * entre iconos YA existentes; ampliar esta lista es la única vía (en código),
 * no hay subida de iconos nuevos.
 */
export interface MaterialIcon {
  /** Nombre Material (valor guardado + ligadura del icono). */
  icon: string;
  /** Etiqueta en español para el dropdown. */
  label: string;
}

export const MATERIAL_ICONS: MaterialIcon[] = [
  // ── Genéricos ──
  { icon: 'category', label: 'Categoría' },
  { icon: 'store_mall_directory', label: 'Directorio de tienda' },
  { icon: 'map', label: 'Mapa' },
  { icon: 'people', label: 'Personas' },
  { icon: 'person', label: 'Persona' },
  { icon: 'badge', label: 'Credencial' },
  { icon: 'schedule', label: 'Horario' },
  { icon: 'event', label: 'Evento' },
  { icon: 'today', label: 'Hoy' },
  { icon: 'calendar_month', label: 'Calendario' },
  { icon: 'inventory_2', label: 'Inventario' },
  { icon: 'inventory', label: 'Inventario (lista)' },
  { icon: 'apartment', label: 'Edificio' },
  { icon: 'work', label: 'Trabajo' },
  { icon: 'home', label: 'Inicio' },
  { icon: 'star', label: 'Estrella' },
  { icon: 'flag', label: 'Bandera' },
  { icon: 'label', label: 'Etiqueta' },
  { icon: 'bookmark', label: 'Marcador' },
  { icon: 'grade', label: 'Valoración' },
  { icon: 'verified', label: 'Verificado' },
  { icon: 'check_circle', label: 'Comprobado' },

  // ── Comercio / tienda / caja ──
  { icon: 'store', label: 'Tienda' },
  { icon: 'storefront', label: 'Escaparate' },
  { icon: 'shopping_cart', label: 'Carrito' },
  { icon: 'shopping_bag', label: 'Bolsa de compra' },
  { icon: 'shopping_basket', label: 'Cesta' },
  { icon: 'local_grocery_store', label: 'Supermercado' },
  { icon: 'point_of_sale', label: 'Terminal de venta (TPV)' },
  { icon: 'sell', label: 'Venta' },
  { icon: 'receipt_long', label: 'Ticket largo' },
  { icon: 'receipt', label: 'Ticket' },
  { icon: 'local_offer', label: 'Oferta' },
  { icon: 'loyalty', label: 'Fidelización' },
  { icon: 'redeem', label: 'Regalo / canje' },
  { icon: 'qr_code', label: 'Código QR' },
  { icon: 'barcode_reader', label: 'Lector de código de barras' },
  { icon: 'payments', label: 'Pagos' },
  { icon: 'euro', label: 'Euro' },
  { icon: 'attach_money', label: 'Dinero' },
  { icon: 'savings', label: 'Ahorro' },
  { icon: 'account_balance_wallet', label: 'Cartera' },
  { icon: 'credit_card', label: 'Tarjeta' },

  // ── Alimentación / secciones de supermercado ──
  { icon: 'restaurant', label: 'Restaurante' },
  { icon: 'restaurant_menu', label: 'Menú' },
  { icon: 'bakery_dining', label: 'Bollería / pan' },
  { icon: 'lunch_dining', label: 'Hamburguesa' },
  { icon: 'dinner_dining', label: 'Cena / plato' },
  { icon: 'brunch_dining', label: 'Brunch' },
  { icon: 'breakfast_dining', label: 'Desayuno' },
  { icon: 'kebab_dining', label: 'Kebab' },
  { icon: 'set_meal', label: 'Pescado / marisco' },
  { icon: 'egg', label: 'Huevo' },
  { icon: 'egg_alt', label: 'Huevo (alt.)' },
  { icon: 'liquor', label: 'Licores' },
  { icon: 'wine_bar', label: 'Vino' },
  { icon: 'sports_bar', label: 'Cerveza' },
  { icon: 'local_cafe', label: 'Café' },
  { icon: 'coffee', label: 'Café (taza)' },
  { icon: 'local_bar', label: 'Cóctel' },
  { icon: 'icecream', label: 'Helado' },
  { icon: 'cake', label: 'Pastel' },
  { icon: 'ramen_dining', label: 'Sopa / ramen' },
  { icon: 'rice_bowl', label: 'Cuenco de arroz' },
  { icon: 'fastfood', label: 'Comida rápida' },
  { icon: 'local_pizza', label: 'Pizza' },
  { icon: 'local_drink', label: 'Bebida' },
  { icon: 'local_dining', label: 'Cubiertos' },
  { icon: 'nutrition', label: 'Nutrición' },
  { icon: 'grass', label: 'Verdura / hierba' },
  { icon: 'agriculture', label: 'Agricultura' },
  { icon: 'eco', label: 'Ecológico' },
  { icon: 'spa', label: 'Bienestar' },
  { icon: 'water_drop', label: 'Agua' },

  // ── Personas / roles / trabajo ──
  { icon: 'groups', label: 'Grupos' },
  { icon: 'engineering', label: 'Ingeniería' },
  { icon: 'support_agent', label: 'Atención al cliente' },
  { icon: 'manage_accounts', label: 'Gestión de cuentas' },
  { icon: 'admin_panel_settings', label: 'Administración' },
  { icon: 'supervisor_account', label: 'Supervisor' },
  { icon: 'handshake', label: 'Acuerdo' },
  { icon: 'cleaning_services', label: 'Limpieza' },
  { icon: 'construction', label: 'Construcción' },
  { icon: 'build', label: 'Herramientas' },
  { icon: 'handyman', label: 'Mantenimiento' },
  { icon: 'checkroom', label: 'Ropa / vestuario' },
  { icon: 'local_laundry_service', label: 'Lavandería' },

  // ── Lugares / logística ──
  { icon: 'warehouse', label: 'Almacén' },
  { icon: 'local_mall', label: 'Centro comercial' },
  { icon: 'kitchen', label: 'Cocina / nevera' },
  { icon: 'local_shipping', label: 'Envío / reparto' },
  { icon: 'directions_car', label: 'Vehículo' },
];
