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
        self.manual_together_groups = []

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
        La compatibilidad se mide ahora como el número de bloques en común
        entre los usuarios.

        Returns:
            Dict con pares de usuarios y su compatibilidad (conteo de bloques comunes)
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
                    common = 0
                else:
                    # Conteo de bloques comunes
                    common = len(avails1 & avails2)

                # Guardar en ambas direcciones
                self.compatibility_matrix[(user1_id, user2_id)] = common
                self.compatibility_matrix[(user2_id, user1_id)] = common

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

    def _flatten_units(self, group_units: List[Dict]) -> List[Dict]:
        """Convierte una lista de unidades de asignación en una lista plana de miembros."""
        members = []
        for unit in group_units:
            members.extend(unit.get('members', []))
        return members

    def _group_member_count(self, group_units: List[Dict]) -> int:
        """Cuenta cuántos usuarios contiene un grupo de unidades."""
        return sum(len(unit.get('member_ids', [])) for unit in group_units)

    def _group_size(self, group_units: List[Dict]) -> int:
        """Alias legible para contar usuarios en un grupo de unidades."""
        return self._group_member_count(group_units)

    def _unit_compatibility_score(self, unit: Dict, group_units: List[Dict]) -> float:
        """
        Calcula la compatibilidad promedio de una unidad con un grupo.
        Si la unidad contiene varios usuarios, también considera su compatibilidad interna.
        """
        unit_members = unit.get('members', [])
        group_members = self._flatten_units(group_units)
        comparisons = []

        if len(unit_members) > 1:
            for index, member1 in enumerate(unit_members):
                for member2 in unit_members[index + 1:]:
                    comparisons.append(self.get_compatibility(member1['id'], member2['id']))

        for unit_member in unit_members:
            for group_member in group_members:
                comparisons.append(self.get_compatibility(unit_member['id'], group_member['id']))

        if not comparisons:
            return 1.0

        return sum(comparisons) / len(comparisons)

    def _build_assignment_units(self, together_groups: List[List[int]]) -> Tuple[List[Dict], List[Dict]]:
        """
        Convierte los grupos manuales en unidades de asignación atómicas.
        """
        member_map = {member['id']: member for member in self.members}
        used_user_ids = set()
        assignment_units = []
        manual_groups_preview = []

        for index, raw_group in enumerate(together_groups or [], start=1):
            if not isinstance(raw_group, (list, tuple)):
                raise ValueError('Cada grupo manual debe ser una lista de usuarios.')

            unique_user_ids = []
            for raw_user_id in raw_group:
                user_id = int(raw_user_id)
                if user_id not in member_map:
                    raise ValueError(f'El usuario {user_id} no pertenece a este grupo.')
                if user_id in used_user_ids:
                    raise ValueError('Un usuario no puede pertenecer a más de un grupo manual.')
                if user_id not in unique_user_ids:
                    unique_user_ids.append(user_id)

            if len(unique_user_ids) < 2:
                raise ValueError('Cada grupo manual debe tener al menos dos usuarios.')

            members = [member_map[user_id] for user_id in unique_user_ids]
            assignment_units.append({
                'manual': True,
                'label': f'Grupo manual {index}',
                'member_ids': unique_user_ids,
                'members': members,
            })
            manual_groups_preview.append({
                'member_ids': unique_user_ids,
                'member_names': [member['name'] for member in members],
            })
            used_user_ids.update(unique_user_ids)

        manual_units = [unit for unit in assignment_units if unit['manual']]
        singleton_units = []

        for member in self.members:
            if member['id'] in used_user_ids:
                continue
            singleton_units.append({
                'manual': False,
                'label': member['name'],
                'member_ids': [member['id']],
                'members': [member],
            })

        manual_units.sort(
            key=lambda unit: (
                -len(unit['member_ids']),
                -sum(member['availability_count'] for member in unit['members']) / len(unit['members'])
            )
        )
        singleton_units.sort(key=lambda unit: unit['members'][0]['availability_count'], reverse=True)

        return manual_units + singleton_units, manual_groups_preview

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
        threshold = config.get('compatibility_threshold', 3)
        rules = config.get('category_rules', [])
        together_groups = config.get('together_groups', [])

        # Cargar miembros y calcular compatibilidad
        self.load_members()
        self.calculate_compatibility_matrix()

        # Construir unidades atómicas de asignación a partir de los grupos manuales
        assignment_units, manual_groups_preview = self._build_assignment_units(together_groups)

        if max_group_size is not None:
            for unit in assignment_units:
                if len(unit['member_ids']) > max_group_size:
                    raise ValueError(
                        f"El grupo manual '{unit['label']}' tiene más usuarios que el tamaño máximo permitido."
                    )

        # Inicializar grupos vacíos
        groups = [[] for _ in range(num_groups)]
        assigned_users = set()

        # Asignación greedy: primero grupos manuales y luego usuarios individuales
        for unit in assignment_units:
            unit_member_ids = unit['member_ids']
            if not allow_multiple and any(user_id in assigned_users for user_id in unit_member_ids):
                continue

            # Buscar grupo donde el usuario ayude a cumplir mínimos y no exceda máximos
            candidate_groups = []
            for idx, group in enumerate(groups):
                if max_group_size and self._group_size(group) + len(unit_member_ids) > max_group_size:
                    continue

                temp_group = group + [unit]
                temp_members = self._flatten_units(temp_group)
                rules_status = self.validate_group_rules(temp_members, rules)

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
                score = self._unit_compatibility_score(unit, group)

                if score < threshold:
                    continue

                # Prioridad: ayuda a cumplir mínimo, luego score
                candidate_groups.append((helps_min, score, idx))

            # Ordenar: primero los que ayudan a cumplir mínimo, luego mayor compatibilidad
            candidate_groups.sort(reverse=True)
            if candidate_groups:
                _, _, best_group_idx = candidate_groups[0]
                groups[best_group_idx].append(unit)
                if not allow_multiple:
                    assigned_users.update(unit_member_ids)
            elif require_all:
                # Si require_all está activado y no encontramos grupo válido,
                # asignar al grupo más pequeño respetando el tamaño máximo cuando sea posible.
                viable_group_indexes = [
                    i for i in range(len(groups))
                    if not max_group_size or self._group_size(groups[i]) + len(unit_member_ids) <= max_group_size
                ]

                if not viable_group_indexes:
                    raise ValueError(
                        f"No hay espacio para asignar el grupo manual '{unit['label']}' sin exceder el tamaño máximo."
                    )

                smallest_group_idx = min(
                    viable_group_indexes,
                    key=lambda i: self._group_size(groups[i])
                )
                groups[smallest_group_idx].append(unit)
                if not allow_multiple:
                    assigned_users.update(unit_member_ids)

        # Fase de reparación: intentar intercambios para cumplir reglas mínimas
        groups = self._repair_groups(groups, rules, max_group_size)

        # Construir preview
        preview = self._build_preview(groups, rules, manual_groups_preview)

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
                    group_members = self._flatten_units(group)
                    count = self.count_condition_matches(group_members, condition)
                    group_member_count = self._group_member_count(group)
                    
                    # Si no cumple el mínimo, buscar un miembro compatible en otros grupos
                    if count < min_required:
                        # Buscar en otros grupos
                        for other_idx, other_group in enumerate(groups):
                            if other_idx == group_idx:
                                continue
                            
                            # Buscar un miembro que cumpla la condición
                            for unit in other_group:
                                unit_members = unit.get('members', [])
                                if any(
                                    self.user_matches_condition(set(member['categories']), condition)
                                    for member in unit_members
                                ):
                                    # Intentar mover o intercambiar
                                    if not max_size or group_member_count + len(unit.get('member_ids', [])) <= max_size:
                                        # Mover directamente
                                        other_group.remove(unit)
                                        group.append(unit)
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

    def _build_preview(self, groups: List[List[Dict]], rules: List[Dict],
                       manual_groups_preview: Optional[List[Dict]] = None) -> Dict:
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

            group_members = self._flatten_units(group)

            # Calcular métricas del grupo
            compatibility_avg = self.calculate_group_compatibility(group_members)
            rules_status = self.validate_group_rules(group_members, rules)

            # Identificar reglas incumplidas
            for rule_status in rules_status:
                if not rule_status['fulfilled']:
                    unfulfilled_rules.add(rule_status['rule'])

            preview_groups.append({
                'id': f'preview-{idx + 1}',
                'name': f'Subgrupo {idx + 1}',
                'members': group_members,
                'compatibility_avg': round(compatibility_avg, 3),
                'rules_status': rules_status
            })

        return {
            'groups': preview_groups,
            'unfulfilled_rules': sorted(unfulfilled_rules),
            'total_members_assigned': sum(len(g['members']) for g in preview_groups),
            'total_members_available': len(self.members),
            'together_groups': manual_groups_preview or []
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
