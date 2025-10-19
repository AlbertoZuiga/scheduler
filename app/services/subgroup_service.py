"""
Servicio para dividir grupos en subgrupos optimizados
basados en compatibilidad horaria y reglas de categorías.
"""
from typing import List, Dict, Set, Tuple, Optional
from collections import defaultdict
import itertools
from app.models.user import User
from app.models.group_member import GroupMember
from app.models.user_availability import UserAvailability
from app.models.group_member_category import GroupMemberCategory


class SubGroupService:
    """
    Servicio principal para la división automática de grupos.
    """

    def __init__(self, parent_group_id: int):
        """
        Inicializa el servicio con el grupo padre.
        
        Args:
            parent_group_id: ID del grupo a dividir
        """
        self.parent_group_id = parent_group_id
        self.members = []
        self.compatibility_matrix = {}
        self.user_categories = {}
        self.user_availability_count = {}

    def load_members(self):
        """
        Carga todos los miembros del grupo con sus categorías.
        """
        members = GroupMember.query.filter_by(
            group_id=self.parent_group_id
        ).all()

        self.members = []
        for member in members:
            # Cargar categorías del miembro
            member_categories = GroupMemberCategory.query.filter_by(
                group_member_id=member.id
            ).all()
            
            category_names = {mc.category.name for mc in member_categories if mc.category}
            
            self.user_categories[member.user_id] = category_names
            
            # Contar disponibilidades del usuario
            avail_count = UserAvailability.query.filter_by(
                user_id=member.user_id
            ).count()
            
            self.user_availability_count[member.user_id] = avail_count
            
            self.members.append({
                'id': member.user_id,
                'name': member.user.name,
                'email': member.user.email,
                'categories': list(category_names),
                'availability_count': avail_count,
                'member_id': member.id
            })

    def calculate_compatibility_matrix(self):
        """
        Calcula la matriz de compatibilidad horaria entre todos los usuarios.
        
        Returns:
            Dict con pares de usuarios y su compatibilidad
        """
        user_ids = [m['id'] for m in self.members]
        
        # Cargar todas las disponibilidades de una vez
        availabilities = UserAvailability.query.filter(
            UserAvailability.user_id.in_(user_ids)
        ).all()
        
        # Organizar por usuario
        user_avails = defaultdict(set)
        for avail in availabilities:
            # Crear identificador único para el slot (día + hora)
            slot_id = f"{avail.availability.weekday}_{avail.availability.hour}"
            user_avails[avail.user_id].add(slot_id)
        
        # Calcular compatibilidad entre cada par
        self.compatibility_matrix = {}
        
        for i, user1_id in enumerate(user_ids):
            for user2_id in user_ids[i+1:]:
                avails1 = user_avails[user1_id]
                avails2 = user_avails[user2_id]
                
                if not avails1 or not avails2:
                    compatibility = 0.0
                else:
                    # Solapamiento de Jaccard
                    intersection = len(avails1 & avails2)
                    union = len(avails1 | avails2)
                    compatibility = intersection / union if union > 0 else 0.0
                
                # Guardar en ambas direcciones
                self.compatibility_matrix[(user1_id, user2_id)] = compatibility
                self.compatibility_matrix[(user2_id, user1_id)] = compatibility
        
        return self.compatibility_matrix

    def get_compatibility(self, user1_id: int, user2_id: int) -> float:
        """
        Obtiene la compatibilidad entre dos usuarios.
        
        Args:
            user1_id: ID del primer usuario
            user2_id: ID del segundo usuario
        
        Returns:
            Valor de compatibilidad (0.0 - 1.0)
        """
        if user1_id == user2_id:
            return 1.0
        return self.compatibility_matrix.get((user1_id, user2_id), 0.0)

    def user_matches_condition(self, user_categories: Set[str], condition: Dict) -> bool:
        """
        Evalúa si un usuario cumple una condición específica.
        
        Args:
            user_categories: Set de categorías del usuario
            condition: Dict con 'categories' y 'operator' ('AND' o 'OR')
        
        Returns:
            True si el usuario cumple la condición
        """
        required_categories = set(condition['categories'])
        operator = condition.get('operator', 'AND')
        
        if operator == 'AND':
            # El usuario debe tener TODAS las categorías
            return required_categories.issubset(user_categories)
        elif operator == 'OR':
            # El usuario debe tener AL MENOS una categoría
            return len(required_categories & user_categories) > 0
        
        return False

    def user_matches_rule(self, user_categories: Set[str], rule: Dict) -> bool:
        """
        Evalúa si un usuario cumple todas las condiciones de una regla.
        
        Args:
            user_categories: Set de categorías del usuario
            rule: Dict con lista de 'conditions'
        
        Returns:
            True si cumple todas las condiciones de la regla
        """
        conditions = rule.get('conditions', [])
        
        # El usuario debe cumplir TODAS las condiciones de la regla
        for condition in conditions:
            if not self.user_matches_condition(user_categories, condition):
                return False
        
        return True

    def count_condition_matches(self, group_members: List[Dict], condition: Dict) -> int:
        """
        Cuenta cuántos miembros del grupo cumplen una condición.
        
        Args:
            group_members: Lista de miembros del grupo
            condition: Condición a evaluar (con categories, operator, min, max)
        
        Returns:
            Número de miembros que cumplen la condición
        """
        count = 0
        for member in group_members:
            user_cats = set(member['categories'])
            if self.user_matches_condition(user_cats, condition):
                count += 1
        return count

    def validate_group_rules(self, group_members: List[Dict], rules: List[Dict]) -> List:
        """
        Valida si un grupo cumple todas las condiciones de todas las reglas.
        Ahora cada condición tiene su propio min/max.
        
        Args:
            group_members: Lista de miembros del grupo
            rules: Lista de reglas, cada una con lista de 'conditions'
        
        Returns:
            Lista con status por cada condición
        """
        conditions_status = []
        condition_idx = 0
        
        for rule in rules:
            conditions = rule.get('conditions', [])
            for condition in conditions:
                condition_idx += 1
                count = self.count_condition_matches(group_members, condition)
                min_required = condition.get('min', 0)
                max_allowed = condition.get('max', float('inf'))
                
                fulfilled = min_required <= count <= max_allowed
                
                conditions_status.append({
                    'rule': condition_idx,
                    'fulfilled': fulfilled,
                    'count': count,
                    'min': min_required,
                    'max': max_allowed if max_allowed != float('inf') else None,
                    'categories': condition.get('categories', []),
                    'operator': condition.get('operator', 'AND')
                })
        
        return conditions_status

    def calculate_group_compatibility(self, group_members: List[Dict]) -> float:
        """
        Calcula la compatibilidad promedio dentro de un grupo.
        
        Args:
            group_members: Lista de miembros del grupo
        
        Returns:
            Compatibilidad promedio (0.0 - 1.0)
        """
        if len(group_members) <= 1:
            return 1.0
        
        total_compat = 0.0
        pairs = 0
        
        for i, member1 in enumerate(group_members):
            for member2 in group_members[i+1:]:
                compat = self.get_compatibility(member1['id'], member2['id'])
                total_compat += compat
                pairs += 1
        
        return total_compat / pairs if pairs > 0 else 0.0

    def generate_subgroups(self, config: Dict) -> Dict:
        """
        Genera subgrupos optimizados según la configuración.
        
        Args:
            config: Configuración con num_groups, max_group_size, 
                    allow_multiple_membership, require_all_members,
                    compatibility_threshold, category_rules
        
        Returns:
            Dict con preview de los grupos generados
        """
        # Extraer configuración
        num_groups = config.get('num_groups', 2)
        max_group_size = config.get('max_group_size', None)
        allow_multiple = config.get('allow_multiple_membership', False)
        require_all = config.get('require_all_members', True)
        threshold = config.get('compatibility_threshold', 0.0)
        rules = config.get('category_rules', [])

        # Cargar miembros y calcular compatibilidad
        self.load_members()
        self.calculate_compatibility_matrix()

        # Inicializar grupos vacíos
        groups = [[] for _ in range(num_groups)]
        assigned_users = set()

        # Ordenar usuarios por disponibilidad (más disponible primero)
        sorted_members = sorted(
            self.members,
            key=lambda m: m['availability_count'],
            reverse=True
        )

        # Asignación greedy mejorada: prioriza cumplir min/max por regla
        for member in sorted_members:
            user_id = member['id']
            if not allow_multiple and user_id in assigned_users:
                continue

            # Buscar grupo donde el usuario ayude a cumplir mínimos y no exceda máximos
            candidate_groups = []
            for idx, group in enumerate(groups):
                if max_group_size and len(group) >= max_group_size:
                    continue

                temp_group = group + [member]
                rules_status = self.validate_group_rules(temp_group, rules)

                # Verificar que no se exceda ningún máximo
                exceeds_max = any(
                    r['count'] > r.get('max', float('inf')) and r.get('max', float('inf')) != float('inf')
                    for r in rules_status
                )
                if exceeds_max:
                    continue

                # Verificar si ayuda a cumplir algún mínimo
                helps_min = any(
                    r['count'] <= r['min'] and r['min'] > 0
                    for r in rules_status
                )

                # Calcular compatibilidad
                if not group:
                    score = 1.0
                else:
                    total_compat = sum(
                        self.get_compatibility(user_id, m['id'])
                        for m in group
                    )
                    score = total_compat / len(group)

                if score < threshold:
                    continue

                # Prioridad: ayuda a cumplir mínimo, luego score
                candidate_groups.append((helps_min, score, idx))

            # Ordenar: primero los que ayudan a cumplir mínimo, luego mayor compatibilidad
            candidate_groups.sort(reverse=True)
            if candidate_groups:
                _, _, best_group_idx = candidate_groups[0]
                groups[best_group_idx].append(member)
                if not allow_multiple:
                    assigned_users.add(user_id)
            elif require_all:
                # Si require_all está activado y no encontramos grupo válido,
                # asignar al grupo más pequeño ignorando threshold y reglas
                smallest_group_idx = min(
                    range(len(groups)),
                    key=lambda i: len(groups[i]) if not max_group_size or len(groups[i]) < max_group_size else float('inf')
                )
                groups[smallest_group_idx].append(member)
                if not allow_multiple:
                    assigned_users.add(user_id)

        # Fase de reparación: intentar intercambios para cumplir reglas mínimas
        groups = self._repair_groups(groups, rules, max_group_size)

        # Construir preview
        preview = self._build_preview(groups, rules)

        return preview

    def _repair_groups(self, groups: List[List[Dict]], rules: List[Dict],
                       max_size: Optional[int]) -> List[List[Dict]]:
        """
        Intenta reparar grupos que no cumplen condiciones mediante intercambios.
        Ahora trabaja con condiciones individuales (cada una con su min/max).
        
        Args:
            groups: Lista de grupos actuales
            rules: Reglas a cumplir (cada una con condiciones)
            max_size: Tamaño máximo por grupo
        
        Returns:
            Lista de grupos reparados
        """
        max_iterations = 50
        iteration = 0

        # Extraer todas las condiciones de todas las reglas
        all_conditions = []
        for rule in rules:
            all_conditions.extend(rule.get('conditions', []))

        while iteration < max_iterations:
            iteration += 1
            made_swap = False

            for condition in all_conditions:
                min_required = condition.get('min', 0)
                
                for group_idx, group in enumerate(groups):
                    count = self.count_condition_matches(group, condition)
                    
                    # Si no cumple el mínimo, buscar un miembro compatible en otros grupos
                    if count < min_required:
                        # Buscar en otros grupos
                        for other_idx, other_group in enumerate(groups):
                            if other_idx == group_idx:
                                continue
                            
                            # Buscar un miembro que cumpla la condición
                            for member in other_group:
                                user_cats = set(member['categories'])
                                if self.user_matches_condition(user_cats, condition):
                                    # Intentar mover o intercambiar
                                    if not max_size or len(group) < max_size:
                                        # Mover directamente
                                        other_group.remove(member)
                                        group.append(member)
                                        made_swap = True
                                        break
                            
                            if made_swap:
                                break
                    
                    if made_swap:
                        break
                
                if made_swap:
                    break
            
            if not made_swap:
                break

        return groups

    def _build_preview(self, groups: List[List[Dict]], rules: List[Dict]) -> Dict:
        """
        Construye el preview final con métricas y validaciones.
        
        Args:
            groups: Lista de grupos generados
            rules: Reglas configuradas
        
        Returns:
            Dict con estructura de preview
        """
        preview_groups = []
        unfulfilled_rules = set()

        for idx, group in enumerate(groups):
            if not group:
                continue

            # Calcular métricas del grupo
            compatibility_avg = self.calculate_group_compatibility(group)
            rules_status = self.validate_group_rules(group, rules)

            # Identificar reglas incumplidas
            for rule_status in rules_status:
                if not rule_status['fulfilled']:
                    unfulfilled_rules.add(rule_status['rule'])

            preview_groups.append({
                'id': f'preview-{idx + 1}',
                'name': f'Subgrupo {idx + 1}',
                'members': group,
                'compatibility_avg': round(compatibility_avg, 3),
                'rules_status': rules_status
            })

        return {
            'groups': preview_groups,
            'unfulfilled_rules': sorted(unfulfilled_rules),
            'total_members_assigned': sum(len(g['members']) for g in preview_groups),
            'total_members_available': len(self.members)
        }


def user_matches_rule(user_categories: Set[str], rule: Dict) -> bool:
    """
    Función auxiliar standalone para evaluar si un usuario cumple una regla.
    No ejecuta eval(), solo usa lógica de conjuntos.
    
    Args:
        user_categories: Set de categorías del usuario
        rule: Dict con 'conditions' (lista de {categories, operator})
    
    Returns:
        True si el usuario cumple todas las condiciones de la regla
    """
    service = SubGroupService(parent_group_id=None)
    return service.user_matches_rule(user_categories, rule)
