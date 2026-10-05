import { Image } from 'expo-image';
import { useEffect, useState } from 'react';
import {
  StyleSheet,
  Text,
  View,
  type ImageSourcePropType,
  type ImageStyle,
  type StyleProp,
  type ViewStyle,
} from 'react-native';

/** Renders a basket item's R2 image, falling back to a name-initial tile
 *  when the verified image manifest has no object for that food. */
export function BasketItemImage({
  imageSource,
  name,
  resizeMode,
  style,
}: {
  imageSource: ImageSourcePropType | null;
  name: string;
  resizeMode?: 'contain' | 'cover';
  style?: StyleProp<ImageStyle>;
}) {
  const [imageFailed, setImageFailed] = useState(false);
  const remoteUri = (
    typeof imageSource === 'object'
    && imageSource !== null
    && 'uri' in imageSource
  ) ? imageSource.uri : null;

  useEffect(() => {
    setImageFailed(false);
  }, [remoteUri]);

  if (!imageSource || imageFailed) {
    return (
      <View
        accessibilityElementsHidden
        style={[styles.fallback, style as StyleProp<ViewStyle>]}
      >
        <Text style={styles.fallbackText}>{name.trim().charAt(0).toUpperCase() || '?'}</Text>
      </View>
    );
  }

  return (
    <Image
      accessibilityElementsHidden
      cachePolicy="memory-disk"
      contentFit={resizeMode ?? 'contain'}
      onError={() => setImageFailed(true)}
      recyclingKey={remoteUri ?? undefined}
      source={imageSource}
      style={style}
    />
  );
}

const styles = StyleSheet.create({
  fallback: {
    alignItems: 'center',
    backgroundColor: '#F1FAF6',
    justifyContent: 'center',
  },
  fallbackText: {
    color: '#087C7E',
    fontSize: 16,
    fontWeight: '700',
  },
});
