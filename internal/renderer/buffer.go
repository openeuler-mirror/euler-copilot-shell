package renderer

import "strings"

// BlockBuffer accumulates text deltas until a complete Markdown block is ready.
type BlockBuffer struct {
	content string
}

func NewBlockBuffer() *BlockBuffer {
	return &BlockBuffer{}
}

func (b *BlockBuffer) Append(delta string) {
	if delta == "" {
		return
	}
	b.content += delta
}

func (b *BlockBuffer) Remaining() string {
	return b.content
}

func (b *BlockBuffer) Reset() {
	b.content = ""
}

// NextCompleteBlock returns the next complete Markdown block, if present.
func (b *BlockBuffer) NextCompleteBlock() (string, bool) {
	if b.content == "" {
		return "", false
	}
	if skip := leadingBlankPrefix(b.content); skip > 0 {
		b.content = b.content[skip:]
		if b.content == "" {
			return "", false
		}
	}

	end := findBlockEnd(b.content)
	if end < 0 {
		return "", false
	}

	block := b.content[:end]
	b.content = b.content[end:]
	return block, true
}

func findBlockEnd(content string) int {
	_, firstLine, complete := nextLine(content, 0)
	if !complete {
		return -1
	}

	if marker, length, ok := codeFenceMarker(firstLine); ok {
		return findFencedBlockEnd(content, marker, length)
	}
	if isATXHeadingLine(firstLine) || isThematicBreakLine(firstLine) {
		end, _, _ := nextLine(content, 0)
		return includeFollowingBlankLine(content, end)
	}
	if isListLine(firstLine) || isQuoteLine(firstLine) {
		return findUntilBlankLine(content)
	}
	return findParagraphEnd(content)
}

func findFencedBlockEnd(content string, marker byte, length int) int {
	pos, _, _ := nextLine(content, 0)
	for pos < len(content) {
		next, line, complete := nextLine(content, pos)
		if !complete {
			return -1
		}
		if isClosingFenceLine(line, marker, length) {
			return includeFollowingBlankLine(content, next)
		}
		pos = next
	}
	return -1
}

func findUntilBlankLine(content string) int {
	pos, _, complete := nextLine(content, 0)
	if !complete {
		return -1
	}
	for pos < len(content) {
		next, line, ok := nextLine(content, pos)
		if !ok {
			return -1
		}
		if isBlankLine(line) {
			return next
		}
		pos = next
	}
	return -1
}

func findParagraphEnd(content string) int {
	pos, _, complete := nextLine(content, 0)
	if !complete {
		return -1
	}
	for pos < len(content) {
		next, line, ok := nextLine(content, pos)
		if !ok {
			return -1
		}
		if isBlankLine(line) {
			return next
		}
		if isATXHeadingLine(line) || isThematicBreakLine(line) || isListLine(line) || isQuoteLine(line) {
			return pos
		}
		if _, _, ok := codeFenceMarker(line); ok {
			return pos
		}
		pos = next
	}
	return -1
}

func includeFollowingBlankLine(content string, end int) int {
	if end >= len(content) {
		return end
	}
	next, line, ok := nextLine(content, end)
	if !ok {
		return end
	}
	if isBlankLine(line) {
		return next
	}
	return end
}

func leadingBlankPrefix(content string) int {
	pos := 0
	for pos < len(content) {
		next, line, ok := nextLine(content, pos)
		if !ok || !isBlankLine(line) {
			return pos
		}
		pos = next
	}
	return pos
}

func nextLine(content string, start int) (int, string, bool) {
	if start >= len(content) {
		return start, "", false
	}
	idx := strings.IndexByte(content[start:], '\n')
	if idx < 0 {
		return len(content), "", false
	}
	next := start + idx + 1
	return next, content[start:next], true
}

func isBlankLine(line string) bool {
	return strings.TrimSpace(line) == ""
}

func isATXHeadingLine(line string) bool {
	trimmed := normalizedBlockLine(line)
	if trimmed == "" || trimmed[0] != '#' {
		return false
	}
	count := 0
	for count < len(trimmed) && trimmed[count] == '#' {
		count++
	}
	if count == 0 || count > 6 {
		return false
	}
	return count == len(trimmed) || trimmed[count] == ' ' || trimmed[count] == '\t'
}

func isQuoteLine(line string) bool {
	trimmed := normalizedBlockLine(line)
	return strings.HasPrefix(trimmed, ">")
}

func isListLine(line string) bool {
	trimmed := normalizedBlockLine(line)
	if len(trimmed) < 2 {
		return false
	}
	if (trimmed[0] == '-' || trimmed[0] == '+' || trimmed[0] == '*') && (trimmed[1] == ' ' || trimmed[1] == '\t') {
		return true
	}
	idx := 0
	for idx < len(trimmed) && trimmed[idx] >= '0' && trimmed[idx] <= '9' {
		idx++
	}
	if idx == 0 || idx+1 >= len(trimmed) {
		return false
	}
	if trimmed[idx] != '.' && trimmed[idx] != ')' {
		return false
	}
	return trimmed[idx+1] == ' ' || trimmed[idx+1] == '\t'
}

func codeFenceMarker(line string) (byte, int, bool) {
	trimmed := normalizedBlockLine(line)
	if len(trimmed) < 3 {
		return 0, 0, false
	}
	marker := trimmed[0]
	if marker != '`' && marker != '~' {
		return 0, 0, false
	}
	count := 0
	for count < len(trimmed) && trimmed[count] == marker {
		count++
	}
	if count < 3 {
		return 0, 0, false
	}
	return marker, count, true
}

func isClosingFenceLine(line string, marker byte, length int) bool {
	trimmed := normalizedBlockLine(line)
	count := 0
	for count < len(trimmed) && trimmed[count] == marker {
		count++
	}
	if count < length {
		return false
	}
	return strings.TrimSpace(trimmed[count:]) == ""
}

func isThematicBreakLine(line string) bool {
	trimmed := strings.TrimSpace(normalizedBlockLine(line))
	if len(trimmed) < 3 {
		return false
	}
	marker := trimmed[0]
	if marker != '-' && marker != '*' && marker != '_' {
		return false
	}
	count := 0
	for i := 0; i < len(trimmed); i++ {
		switch trimmed[i] {
		case byte(marker):
			count++
		case ' ', '\t':
		default:
			return false
		}
	}
	return count >= 3
}

func normalizedBlockLine(line string) string {
	trimmed := strings.TrimRight(line, "\r\n")
	spaces := 0
	for spaces < len(trimmed) && spaces < 3 && trimmed[spaces] == ' ' {
		spaces++
	}
	return trimmed[spaces:]
}
