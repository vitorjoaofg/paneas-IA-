"""
Room Manager Service

Gerencia salas para simulação de atendimento call center com dual-speaker.
Cada sala pode ter até 2 participantes: agent (atendente) e client (cliente).
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Optional, Set
import logging

logger = logging.getLogger(__name__)


class RoomStatus(str, Enum):
    """Status possíveis de uma sala"""
    WAITING = "waiting"  # Aguardando segundo participante
    ACTIVE = "active"    # Ambos participantes conectados
    CLOSED = "closed"    # Sala fechada


class SpeakerRole(str, Enum):
    """Papéis dos participantes"""
    AGENT = "agent"      # Atendente
    CLIENT = "client"    # Cliente


@dataclass
class Room:
    """
    Representa uma sala de atendimento com 2 participantes.

    Attributes:
        room_id: Identificador único da sala
        agent_session_id: ID da sessão do atendente
        client_session_id: ID da sessão do cliente
        agent_transcript: Transcrição acumulada do atendente
        client_transcript: Transcrição acumulada do cliente
        status: Status atual da sala
        created_at: Timestamp de criação
        participants: Set com session_ids dos participantes
    """
    room_id: str
    agent_session_id: Optional[str] = None
    client_session_id: Optional[str] = None
    agent_transcript: str = ""
    client_transcript: str = ""
    status: RoomStatus = RoomStatus.WAITING
    created_at: datetime = field(default_factory=datetime.now)
    participants: Set[str] = field(default_factory=set)

    def add_participant(self, session_id: str, role: SpeakerRole) -> bool:
        """
        Adiciona participante à sala.

        Args:
            session_id: ID da sessão WebSocket
            role: Papel do participante (agent ou client)

        Returns:
            True se adicionado com sucesso, False se sala já está cheia
        """
        if len(self.participants) >= 2:
            logger.warning(f"Tentativa de adicionar 3º participante à sala {self.room_id}")
            return False

        self.participants.add(session_id)

        if role == SpeakerRole.AGENT:
            if self.agent_session_id is not None:
                logger.warning(f"Sala {self.room_id} já tem atendente, sobrescrevendo")
            self.agent_session_id = session_id
        elif role == SpeakerRole.CLIENT:
            if self.client_session_id is not None:
                logger.warning(f"Sala {self.room_id} já tem cliente, sobrescrevendo")
            self.client_session_id = session_id

        # Atualiza status
        if len(self.participants) == 2:
            self.status = RoomStatus.ACTIVE
            logger.info(f"Sala {self.room_id} agora está ATIVA com 2 participantes")

        return True

    def remove_participant(self, session_id: str) -> None:
        """Remove participante da sala"""
        if session_id in self.participants:
            self.participants.remove(session_id)

            if session_id == self.agent_session_id:
                self.agent_session_id = None
            elif session_id == self.client_session_id:
                self.client_session_id = None

            # Atualiza status
            if len(self.participants) == 0:
                self.status = RoomStatus.CLOSED
            elif len(self.participants) == 1:
                self.status = RoomStatus.WAITING

            logger.info(f"Participante {session_id} removido da sala {self.room_id}")

    def get_role(self, session_id: str) -> Optional[SpeakerRole]:
        """Retorna o papel de um participante"""
        if session_id == self.agent_session_id:
            return SpeakerRole.AGENT
        elif session_id == self.client_session_id:
            return SpeakerRole.CLIENT
        return None

    def get_other_session_id(self, session_id: str) -> Optional[str]:
        """Retorna o session_id do outro participante"""
        if session_id == self.agent_session_id:
            return self.client_session_id
        elif session_id == self.client_session_id:
            return self.agent_session_id
        return None

    def update_transcript(self, role: SpeakerRole, transcript: str) -> None:
        """Atualiza transcrição de um participante"""
        if role == SpeakerRole.AGENT:
            self.agent_transcript = transcript
        elif role == SpeakerRole.CLIENT:
            self.client_transcript = transcript

    def get_combined_transcript(self) -> str:
        """Retorna transcrição combinada para insights"""
        parts = []
        if self.agent_transcript:
            parts.append(f"Atendente: {self.agent_transcript}")
        if self.client_transcript:
            parts.append(f"Cliente: {self.client_transcript}")
        return "\n\n".join(parts)

    def is_full(self) -> bool:
        """Verifica se sala está cheia"""
        return len(self.participants) >= 2

    def is_empty(self) -> bool:
        """Verifica se sala está vazia"""
        return len(self.participants) == 0


class RoomManager:
    """
    Gerenciador global de salas.

    Mantém estado em memória das salas ativas.
    Para ambientes multi-instância, considere usar Redis.
    """

    def __init__(self):
        self._rooms: Dict[str, Room] = {}
        logger.info("RoomManager inicializado")

    def create_room(self, room_id: str) -> Room:
        """
        Cria uma nova sala.

        Args:
            room_id: Identificador da sala

        Returns:
            Objeto Room criado
        """
        if room_id in self._rooms:
            logger.warning(f"Sala {room_id} já existe, retornando existente")
            return self._rooms[room_id]

        room = Room(room_id=room_id)
        self._rooms[room_id] = room
        logger.info(f"Sala {room_id} criada")
        return room

    def get_room(self, room_id: str) -> Optional[Room]:
        """Retorna sala pelo ID"""
        return self._rooms.get(room_id)

    def get_or_create_room(self, room_id: str) -> Room:
        """Retorna sala existente ou cria nova"""
        if room_id in self._rooms:
            return self._rooms[room_id]
        return self.create_room(room_id)

    def join_room(self, room_id: str, session_id: str, role: str) -> Room:
        """
        Adiciona participante a uma sala.

        Args:
            room_id: ID da sala
            session_id: ID da sessão WebSocket
            role: Papel do participante ("agent" ou "client")

        Returns:
            Objeto Room atualizado

        Raises:
            ValueError: Se sala está cheia ou role inválido
        """
        # Valida role
        try:
            speaker_role = SpeakerRole(role)
        except ValueError:
            raise ValueError(f"Role inválido: {role}. Use 'agent' ou 'client'")

        # Cria ou obtém sala
        room = self.get_or_create_room(room_id)

        # Adiciona participante
        success = room.add_participant(session_id, speaker_role)
        if not success:
            raise ValueError(f"Sala {room_id} já está cheia (2 participantes)")

        logger.info(
            f"Participante {session_id} ({role}) entrou na sala {room_id}. "
            f"Status: {room.status}, Participantes: {len(room.participants)}"
        )

        return room

    def leave_room(self, room_id: str, session_id: str) -> None:
        """
        Remove participante de uma sala.

        Args:
            room_id: ID da sala
            session_id: ID da sessão
        """
        room = self.get_room(room_id)
        if not room:
            logger.warning(f"Tentativa de sair de sala inexistente: {room_id}")
            return

        room.remove_participant(session_id)

        # Remove sala se está vazia
        if room.is_empty():
            del self._rooms[room_id]
            logger.info(f"Sala {room_id} removida (vazia)")

    def update_transcript(
        self,
        room_id: str,
        session_id: str,
        transcript: str
    ) -> Optional[Room]:
        """
        Atualiza transcrição de um participante.

        Args:
            room_id: ID da sala
            session_id: ID da sessão
            transcript: Texto da transcrição

        Returns:
            Room atualizado ou None se sala não existe
        """
        room = self.get_room(room_id)
        if not room:
            logger.warning(f"Tentativa de atualizar transcrição em sala inexistente: {room_id}")
            return None

        role = room.get_role(session_id)
        if not role:
            logger.warning(f"Session {session_id} não encontrada na sala {room_id}")
            return None

        room.update_transcript(role, transcript)
        logger.debug(f"Transcrição atualizada para {role} na sala {room_id}")

        return room

    def get_room_by_session(self, session_id: str) -> Optional[Room]:
        """Encontra sala que contém determinada sessão"""
        for room in self._rooms.values():
            if session_id in room.participants:
                return room
        return None

    def cleanup_closed_rooms(self) -> int:
        """
        Remove salas fechadas.

        Returns:
            Número de salas removidas
        """
        closed_rooms = [
            room_id for room_id, room in self._rooms.items()
            if room.status == RoomStatus.CLOSED
        ]

        for room_id in closed_rooms:
            del self._rooms[room_id]

        if closed_rooms:
            logger.info(f"Removidas {len(closed_rooms)} salas fechadas")

        return len(closed_rooms)

    def get_stats(self) -> dict:
        """Retorna estatísticas das salas"""
        total = len(self._rooms)
        waiting = sum(1 for r in self._rooms.values() if r.status == RoomStatus.WAITING)
        active = sum(1 for r in self._rooms.values() if r.status == RoomStatus.ACTIVE)
        closed = sum(1 for r in self._rooms.values() if r.status == RoomStatus.CLOSED)

        return {
            "total_rooms": total,
            "waiting": waiting,
            "active": active,
            "closed": closed
        }


# Instância global singleton
room_manager = RoomManager()
