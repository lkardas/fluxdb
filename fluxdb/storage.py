import uuid
import struct
from typing import Dict, Optional
from .exceptions import RecordEncodingError

class StorageBackend:
    """Base class for storage backends in FluxDB."""
    def encode_record(self, data: Dict) -> bytes:
        raise NotImplementedError

    def decode_record(self, data: bytes) -> Optional[Dict]:
        raise NotImplementedError

class BinaryStorage(StorageBackend):
    """Binary storage backend using struct for encoding/decoding records."""
    def encode_record(self, data: Dict) -> bytes:
        """Encodes a record into a binary format.

        Args:
            data (Dict): Record to encode.

        Returns:
            bytes: Encoded record.

        Raises:
            RecordEncodingError: If encoding fails.
        """
        try:
            record_id = data.get('_id', str(uuid.uuid4()))
            data['_id'] = record_id
            # Кодируем record_id как строку UTF-8, дополняя до 36 байт
            record_id_bytes = record_id.encode('utf-8').ljust(36, b'\0')[:36]
            parts = [struct.pack('!I', len(data))]
            for key, value in data.items():
                key_str = str(key)
                value_str = str(value)
                key_bytes = key_str.encode('utf-8')
                value_bytes = value_str.encode('utf-8')
                parts.append(
                    struct.pack('!I', len(key_bytes)) + key_bytes +
                    struct.pack('!I', len(value_bytes)) + value_bytes
                )
            body = b''.join(parts)
            return struct.pack('!I', len(body) + 36) + record_id_bytes + body
        except (struct.error, ValueError, UnicodeEncodeError) as e:
            raise RecordEncodingError(f"Failed to encode record: {e}")

    def decode_record(self, data: bytes) -> Optional[Dict]:
        """Decodes a record from a binary format.

        Args:
            data (bytes): Binary data to decode.

        Returns:
            Optional[Dict]: Decoded record or None if decoding fails.
        """
        try:
            if len(data) < 36:
                return None
            record = {}
            # Декодируем первые 36 байт как строку UTF-8, убирая нулевые байты
            record_id = data[:36].rstrip(b'\0').decode('utf-8', errors='ignore')
            record['_id'] = record_id
            offset = 36
            if len(data) < offset + 4:
                return None
            num_fields = struct.unpack('!I', data[offset:offset+4])[0]
            offset += 4
            for _ in range(num_fields):
                if len(data) < offset + 4:
                    return None
                key_len = struct.unpack('!I', data[offset:offset+4])[0]
                offset += 4
                if len(data) < offset + key_len:
                    return None
                key = data[offset:offset+key_len].decode('utf-8', errors='ignore')
                offset += key_len
                if len(data) < offset + 4:
                    return None
                value_len = struct.unpack('!I', data[offset:offset+4])[0]
                offset += 4
                if len(data) < offset + value_len:
                    return None
                value = data[offset:offset+value_len].decode('utf-8', errors='ignore')
                offset += value_len
                record[key] = value
            return record
        except (struct.error, ValueError, UnicodeDecodeError):
            return None
